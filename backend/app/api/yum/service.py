"""Orchestration for POST /scenarios/yum/negotiate and the save/list/get/
delete/toggle-favorite endpoints under it.

This replicates what the reference project's llm-agent/agents.py::
GlovisAgent.run() does *around* its LLM negotiation calls — route search,
deadline filter, priority-axis sort, top_k pick, response shaping — but with
the negotiation itself removed: each leg's listed cost_usd/total_days is
used directly (no per-leg LLM accept/counter/reject), and the final ranking
for every axis is done by the rule-based app.scenario.ranking module instead
of one LLM ranking call plus rule-based fallbacks for the rest.

Runs as a FastAPI BackgroundTasks job (see progress.py) purely for parity
with the reference's async job/polling contract — the search itself is fast
(well under a second), unlike the reference's 1-7+ minute LLM negotiation.
"""
from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any, Optional

from app.dataset import yum_loader as loader
from app.dataset.schema import NormalizedService
from app.planning.ceu import ceu_multiplier
from app.planning.route_search import RouteCandidate, find_routes
from app.scenario import ranking
from app.scenario.store import ScenarioStore

from .glovis_bridge import list_nodes  # noqa: F401  (re-exported for router parity)
from .llm_bridge import run_frontend_request
from .progress import complete_job, fail_job, make_progress
from .schemas import NegotiationRequest, SaveRouteRequest
from .store_bridge import find_by_source, get_store

logger = logging.getLogger(__name__)

MAX_HOPS = 3

# Hyundai Glovis self-operated leg detection, ported from
# llm-agent/agents.py::is_own_leg (minus the GLOVIS_STANDIN_BY_DATASET
# fallback, which only applied to three retired datasets this project never
# loads).
GLOVIS_MARKERS = ("GLOVIS", "글로비스")

# Short carrier tags for route_id generation, ported from
# glovis_scenario/engine.py::SHORT.
SHORT = {
    "HYUNDAI_GLOVIS_SEA": "GLV", "DB_CARGO": "DB", "RAIL_CARGO_GROUP": "RCG",
    "KOREA_CARLINE": "KCL", "DAEHAN_TRANS": "DHT",
    "EUROTRANS_AUTO": "ETA", "DSV_ROAD": "DSV",
    "KOREAN_AIR_CARGO": "KE", "LUFTHANSA_CARGO": "LH",
}


def is_own_leg(leg: NormalizedService) -> bool:
    if leg.carrier_role == "OWN_FLEET":
        return True
    hay = f"{leg.carrier_id} {leg.carrier_name}".upper()
    return any(m in hay for m in GLOVIS_MARKERS) or "글로비스" in leg.carrier_name


def _make_route_id(legs: list[NormalizedService], used_ids: dict[str, int]) -> str:
    tags: list[str] = []
    seen: set[str] = set()
    for l in legs:
        tag = SHORT.get(l.carrier_id, l.carrier_id[:3].upper())
        if tag not in seen:
            seen.add(tag)
            tags.append(tag)
    hub = next((l.destination for l in legs if l.mode == "sea"), legs[-1].destination)
    base = f"ROUTE-{hub}-" + "-".join(tags)
    used_ids[base] = used_ids.get(base, 0) + 1
    return base if used_ids[base] == 1 else f"{base}-{used_ids[base]}"


def _make_label(legs: list[NormalizedService]) -> str:
    hub = next((l.destination for l in legs if l.mode == "sea"), None)
    modes = "+".join(dict.fromkeys(l.mode for l in legs))
    return f"{loader.display_name(hub)} 경유 {modes}" if hub else modes


def _candidate_sort_dict(rc: RouteCandidate) -> dict[str, Any]:
    return {"metrics": {
        "cost_usd_per_vehicle": rc.total_cost_usd,
        "total_days": rc.total_days,
        "co2_kg_per_vehicle": rc.total_co2_kg,
        "reliability": rc.reliability,
    }}


def _route_to_option(route: RouteCandidate, quantity: int, used_ids: dict[str, int]) -> dict[str, Any]:
    legs_out = []
    n_self = 0
    for i, l in enumerate(route.legs, 1):
        self_op = is_own_leg(l)
        if self_op:
            n_self += 1
        raw_o = l.raw.get("origin", {})
        raw_d = l.raw.get("destination", {})
        legs_out.append({
            "sequence": i,
            "carrier_id": l.carrier_id,
            "carrier_name": l.carrier_name,
            "service_id": l.service_id,
            "mode": l.mode,
            "self_operated": self_op,
            "origin": l.origin,
            "destination": l.destination,
            "origin_node_id": raw_o.get("node_id", l.origin),
            "destination_node_id": raw_d.get("node_id", l.destination),
            "listed_cost_usd_per_vehicle": round(l.cost_usd, 2),
            "days": round(l.total_days, 2),
            "co2_kg_per_vehicle": round(l.co2_kg or 0.0, 2),
            "reliability": round(l.reliability_score, 4),
        })

    cost_per_vehicle = round(route.total_cost_usd, 2)
    co2_per_vehicle = round(route.total_co2_kg, 2)
    return {
        "route_id": _make_route_id(route.legs, used_ids),
        "label": _make_label(route.legs),
        "path": [route.legs[0].origin] + [l.destination for l in route.legs],
        "modes": [l.mode for l in route.legs],
        "feasible": True,
        "metrics": {
            "cost_usd_per_vehicle": cost_per_vehicle,
            "shipment_cost_usd": round(cost_per_vehicle * quantity, 2),
            "total_days": round(route.total_days, 2),
            "co2_kg_per_vehicle": co2_per_vehicle,
            "shipment_co2_kg": round(co2_per_vehicle * quantity, 2),
            "reliability": round(route.reliability, 4),
            "transfers": len(route.legs) - 1,
        },
        "legs_self_operated": n_self,
        "legs": legs_out,
    }


def _base_request_block(req: NegotiationRequest) -> dict[str, Any]:
    return {
        "origin": req.origin, "destination": req.destination,
        "cargo": req.vehicle_type, "priority": req.selected_axis,
        "quantity": req.quantity, "vehicle_type": req.vehicle_type,
    }


def _run_real_agent(request_id: str, req: NegotiationRequest, on_progress=None) -> dict[str, Any]:
    """Run the bundled Glovis/Carrier agents and normalize their result for the UI."""
    agent_axis = "BALANCED" if req.selected_axis == "RELIABILITY" else req.selected_axis
    raw = run_frontend_request(
        dataset_name="ver6", origin=req.origin, destination=req.destination,
        cargo=req.vehicle_type, quantity=req.quantity, top_k=req.top_k,
        priorities=(agent_axis,), save_trace=True, on_progress=on_progress,
    )
    if raw.get("status") != "completed":
        return {
            "schema_version": "1.0.0", "request_id": request_id, "status": "no_route",
            "error": "; ".join(raw.get("warnings", [])) or "No feasible route found.",
            "request": _base_request_block(req), "search_summary": raw.get("search_summary", {}),
            "recommendation_sets": {}, "routes": [], "customs": raw.get("customs", {}),
            "incoterm": raw.get("incoterm", {}), "negotiation": raw.get("negotiation", {"trace": [], "grounding": {}}),
            "warnings": raw.get("warnings", []),
        }

    services = {service.service_id: service for service in loader.get_services()}
    routes: list[dict[str, Any]] = []
    for route in raw.get("routes", []):
        legs, self_operated = [], 0
        for sequence, leg in enumerate(route.get("legs", []), 1):
            service = services.get(leg["service_id"])
            origin_raw = (service.raw.get("origin", {}) if service else {}) or {}
            destination_raw = (service.raw.get("destination", {}) if service else {}) or {}
            is_self = bool(leg.get("self_operated"))
            self_operated += int(is_self)
            legs.append({
                "sequence": sequence,
                "carrier_id": leg["carrier_id"], "carrier_name": leg["carrier_name"],
                "service_id": leg["service_id"], "mode": leg["mode"], "self_operated": is_self,
                "origin": leg["origin"], "destination": leg["destination"],
                "origin_node_id": origin_raw.get("node_id", leg["origin"]),
                "destination_node_id": destination_raw.get("node_id", leg["destination"]),
                "listed_cost_usd_per_vehicle": leg.get("agreed_cost_usd_per_vehicle") or leg.get("listed_cost_usd_per_vehicle", 0),
                "days": leg.get("days", 0), "co2_kg_per_vehicle": leg.get("co2_kg_per_vehicle", 0),
                "reliability": leg.get("reliability", 0),
            })
        metrics = dict(route["metrics"])
        metrics["shipment_co2_kg"] = round(metrics.get("co2_kg_per_vehicle", 0) * req.quantity, 2)
        routes.append({**route, "metrics": metrics, "legs": legs, "legs_self_operated": self_operated})

    if req.max_transit_days is not None:
        routes = [route for route in routes if route["metrics"]["total_days"] <= req.max_transit_days]
    agent_metrics = raw.get("agent_metrics", {})
    if not routes:
        return {
            "schema_version": "1.0.0", "request_id": request_id, "status": "no_route",
            "error": f"납기 제약(최대 {req.max_transit_days}일)을 만족하는 경로가 없습니다.",
            "request": _base_request_block(req), "search_summary": raw.get("search_summary", {}),
            "recommendation_sets": {}, "routes": [], "customs": raw.get("customs", {}),
            "incoterm": raw.get("incoterm", {}), "negotiation": raw.get("negotiation", {"trace": [], "grounding": {}}),
            "warnings": raw.get("warnings", []),
        }
    return {
        "schema_version": "1.0.0", "request_id": request_id, "status": "completed", "error": None,
        "request": _base_request_block(req),
        "search_summary": {**raw.get("search_summary", {}), "excluded_by_deadline": 0,
                           "llm_calls": agent_metrics.get("llm_calls", 0),
                           "elapsed_sec": agent_metrics.get("wall_clock_sec", 0)},
        "recommendation_sets": ranking.build_recommendation_sets(routes),
        "routes": routes, "customs": raw.get("customs", {}), "incoterm": raw.get("incoterm", {}),
        "negotiation": raw.get("negotiation", {"trace": [], "grounding": {}}),
        "warnings": raw.get("warnings", []),
    }


def run_negotiation_job(request_id: str, req: NegotiationRequest) -> None:
    """BackgroundTasks에서 돌아간다. 예외를 밖으로 던지면 안 된다 — 호출부에
    아무도 못 받는다(job 상태로만 알린다). 실제로는 LLM 협상이 없어서
    수십 밀리초면 끝나지만, 폴링 계약(create_job 이후 GET으로 진행 상황을
    조회하는 구조)은 참고 프로젝트와 동일하게 유지한다.
    """
    on_progress = make_progress(request_id)
    started = time.perf_counter()
    try:
        result = _run_real_agent(request_id, req, on_progress=on_progress)
        on_progress({"stage": "complete", "status": "done"})
        complete_job(request_id, result)
        return

        on_progress({"stage": "route_search", "status": "start",
                     "origin": req.origin, "destination": req.destination})

        services = loader.get_services()
        # CEU-scale cost *before* search — ranking by COST has to sort on
        # the price for the vehicle actually being shipped, not the
        # SEDAN-equivalent baseline every service in this dataset is stored
        # at (ported from llm-agent/agents.py::GlovisAgent.run).
        mult = ceu_multiplier(req.vehicle_type)
        if mult != 1.0:
            services = [
                replace(s, cost_usd=s.cost_usd * mult) if s.allowed_vehicle_types is not None else s
                for s in services
            ]

        all_routes = find_routes(services, req.origin, req.destination,
                                  max_hops=MAX_HOPS, vehicle_type=req.vehicle_type)
        candidate_routes_found = len(all_routes)

        routes = all_routes
        excluded_by_deadline = 0
        if req.max_transit_days is not None:
            within = [r for r in all_routes if r.total_days <= req.max_transit_days]
            excluded_by_deadline = len(all_routes) - len(within)
            routes = within

        if not routes:
            if candidate_routes_found and excluded_by_deadline == candidate_routes_found:
                on_progress({"stage": "route_search", "status": "deadline_infeasible",
                             "max_transit_days": req.max_transit_days, "n_candidates": candidate_routes_found})
                error = (
                    f"납기 제약(최대 {req.max_transit_days}일)을 만족하는 경로가 없습니다 — "
                    f"후보 {candidate_routes_found}개 전부 기각. "
                    "출발가능일을 앞당기거나 납기를 늘려서 다시 시도해보세요."
                )
            else:
                on_progress({"stage": "route_search", "status": "no_routes"})
                error = f"{req.origin} → {req.destination} 구간에 대한 경로를 찾을 수 없습니다."
            complete_job(request_id, {
                "schema_version": "1.0.0",
                "request_id": request_id,
                "status": "no_route",
                "error": error,
                "request": _base_request_block(req),
                "search_summary": {
                    "candidate_routes_found": candidate_routes_found,
                    "excluded_by_deadline": excluded_by_deadline,
                    "routes_returned": 0,
                    "llm_calls": 0,
                    "elapsed_sec": round(time.perf_counter() - started, 4),
                },
                "recommendation_sets": {},
                "routes": [],
                "customs": {},
                "incoterm": {"code": None, "version": "Incoterms 2020"},
                "negotiation": {
                    "trace": [],
                    "grounding": {
                        "total_leg_negotiations": 0, "grounded": 0, "hallucinated": 0,
                        "deals_rejected_or_walked": 0, "legs_self_operated_by_glovis": 0,
                        "legs_externally_negotiated": 0,
                    },
                },
                "warnings": [],
            })
            return

        on_progress({"stage": "route_search", "status": "done", "n_routes_found": candidate_routes_found})
        if excluded_by_deadline:
            on_progress({"stage": "route_search", "status": "deadline_filtered",
                         "n_excluded": excluded_by_deadline, "n_remaining": len(routes)})

        on_progress({"stage": "ranking", "status": "start"})

        # Sort candidates by the requested priority axis (same AXIS_KEYS
        # used for the final recommendation sets below), dedupe by leg
        # signature, keep the top_k — mirrors GlovisAgent.run's candidate
        # selection.
        key_fn = ranking.AXIS_KEYS[req.selected_axis]
        ordered = sorted(routes, key=lambda rc: key_fn(_candidate_sort_dict(rc)))

        seen_sigs: set[tuple] = set()
        picked: list[RouteCandidate] = []
        for rc in ordered:
            sig = tuple((l.carrier_id, l.origin, l.destination) for l in rc.legs)
            if sig in seen_sigs:
                continue
            seen_sigs.add(sig)
            picked.append(rc)
            if len(picked) >= req.top_k:
                break

        used_ids: dict[str, int] = {}
        route_options = [_route_to_option(rc, req.quantity, used_ids) for rc in picked]
        recommendation_sets = ranking.build_recommendation_sets(route_options)

        n_self_total = sum(r["legs_self_operated"] for r in route_options)
        n_legs_total = sum(len(r["legs"]) for r in route_options)

        on_progress({"stage": "ranking", "status": "done"})
        on_progress({"stage": "complete", "status": "done"})

        warnings = []
        if excluded_by_deadline:
            warnings.append(f"납기 제약으로 {excluded_by_deadline}개 후보가 제외되었습니다.")

        result = {
            "schema_version": "1.0.0",
            "request_id": request_id,
            "status": "completed",
            "error": None,
            "request": _base_request_block(req),
            "search_summary": {
                "candidate_routes_found": candidate_routes_found,
                "excluded_by_deadline": excluded_by_deadline,
                "routes_returned": len(route_options),
                "llm_calls": 0,
                "elapsed_sec": round(time.perf_counter() - started, 4),
            },
            "recommendation_sets": recommendation_sets,
            "routes": route_options,
            "customs": {},
            "incoterm": {"code": None, "version": "Incoterms 2020"},
            # 실제 LLM 협상이 없으므로 trace는 항상 비어 있고, grounding은
            # "협상 자체가 없었다"는 사실을 그대로 보여준다 — 자사(글로비스)
            # 운항 구간만 grounded=0/hallucinated=0인 채로 집계된다.
            "negotiation": {
                "trace": [],
                "grounding": {
                    "total_leg_negotiations": 0,
                    "grounded": 0,
                    "hallucinated": 0,
                    "deals_rejected_or_walked": 0,
                    "legs_self_operated_by_glovis": n_self_total,
                    "legs_externally_negotiated": n_legs_total - n_self_total,
                },
            },
            "warnings": warnings,
        }
        complete_job(request_id, result)
    except Exception as exc:  # noqa: BLE001 — 백그라운드 작업 경계, 반드시 여기서 막는다
        logger.exception("search job %s failed", request_id)
        fail_job(request_id, str(exc))


def _parse_etd(etd) -> Optional[datetime]:
    if not etd:
        return None
    if isinstance(etd, datetime):
        return etd
    try:
        return datetime.fromisoformat(str(etd))
    except ValueError:
        return None


def save_route(request_id: str, job_result: dict[str, Any], body: SaveRouteRequest) -> dict[str, Any]:
    """탐색 결과의 route 하나를 실제 시나리오로 저장한다.

    같은 (request_id, route_id) 조합으로 다시 호출되면(북마크 버튼→경로선택
    버튼 순서든 반대든) 새 scenario_id를 만들지 않고 같은 행을 덮어쓴다.
    is_favorite는 한쪽이라도 true였으면 true로 유지한다.
    """
    route = next((r for r in job_result["routes"] if r["route_id"] == body.route_id), None)
    if route is None:
        raise KeyError(body.route_id)

    req = job_result["request"]
    store = get_store()

    existing_id = find_by_source(store, request_id, body.route_id)
    if existing_id:
        existing = store.get(existing_id, tracking=False)
        scenario_id = existing_id
        effective_favorite = bool(body.is_favorite) or bool(existing.get("is_favorite"))
        existing_status = existing.get("status")
    else:
        scenario_id = store.next_id()
        effective_favorite = bool(body.is_favorite)
        existing_status = None

    # "이 경로 선택"(is_favorite=False로 오는 호출)은 운송 추적에 뜨도록
    # 실행 확정(CONFIRMED)까지 시킨다 — 순수 북마크(is_favorite=True)는
    # DRAFT로 남겨 두되, 이미 확정된 걸 다시 북마크만 해도 뒤로 안 돌린다.
    effective_status = "CONFIRMED" if not body.is_favorite else (existing_status or "DRAFT")

    etd = _parse_etd(body.etd) or (datetime.now() + timedelta(days=7))
    eta = etd + timedelta(days=route["metrics"]["total_days"])

    origin_name = loader.display_name(req["origin"])
    destination_name = loader.display_name(req["destination"])
    name = body.scenario_name or f"{origin_name} → {destination_name}"

    legs = []
    cur = etd
    for l in route["legs"]:
        days = l["days"] or 0.0
        leg_etd, leg_eta = cur, cur + timedelta(days=days)
        legs.append({
            "sequence": l["sequence"], "mode": l["mode"],
            "carrier_id": l["carrier_id"], "carrier_name": l["carrier_name"],
            "service_id": l["service_id"], "service_tier": None,
            "source_dataset": "ver6",
            "origin_node_id": l["origin_node_id"], "origin_location_id": l["origin"],
            "origin_name": loader.display_name(l["origin"]),
            "destination_node_id": l["destination_node_id"], "destination_location_id": l["destination"],
            "destination_name": loader.display_name(l["destination"]),
            "distance_km": None,
            "cost_usd_per_vehicle": l["listed_cost_usd_per_vehicle"],
            "transit_hours": round(days * 24, 1),
            "co2_kg_per_vehicle": l["co2_kg_per_vehicle"],
            "reliability": l["reliability"],
            "etd": leg_etd.isoformat(timespec="minutes"),
            "eta": leg_eta.isoformat(timespec="minutes"),
            "atd": None, "ata": None,
            "expected_delay_hours": None, "delay_reason": None,
        })
        cur = leg_eta

    sc = {
        "scenario_id": scenario_id,
        "scenario_name": name,
        "status": effective_status,
        "is_favorite": effective_favorite,
        "created_at": datetime.now().isoformat(timespec="minutes"),
        "selected_axis": req["priority"],
        "source_request_id": request_id,
        "source_route_id": body.route_id,
        "cargo": {
            "cargo_type": "FINISHED_VEHICLE",
            "vehicle_type": req["vehicle_type"],
            "quantity": req["quantity"],
            "quantity_unit": "vehicle",
        },
        "route": {
            "origin_node_id": route["legs"][0]["origin_node_id"],
            "origin_location_id": req["origin"],
            "origin_name": origin_name,
            "destination_node_id": route["legs"][-1]["destination_node_id"],
            "destination_location_id": req["destination"],
            "destination_name": destination_name,
            "path": route["path"],
            "modes": route["modes"],
            "leg_count": len(route["legs"]),
        },
        "metrics": {**route["metrics"], "customs_days": None},
        "schedule": {
            "etd": etd.isoformat(timespec="minutes"),
            "eta": eta.isoformat(timespec="minutes"),
            "total_transit_hours": round(route["metrics"]["total_days"] * 24, 1),
        },
        "trade": {},
        "legs": legs,
    }
    store.save(sc)
    saved = store.get(scenario_id)
    assert saved is not None
    return saved
