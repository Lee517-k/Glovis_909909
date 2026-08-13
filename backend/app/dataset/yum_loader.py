"""Loads the ver6 carrier-service dataset (backend/app/dataset/service_data/*.json)
into NormalizedService records, and builds the node registry used by the
GET /api/scenario/nodes endpoint.

Ported from the reference project's llm-agent/adapters.py::load_ver6 (+ the
shared _load_node_graph_family helpers it calls) and
backend/app/yum/glovis_bridge.py::list_nodes / glovis_scenario/engine.py's
node-registry globals — collapsed into one module since this project only
ever loads a single dataset (ver6), unlike the reference's 6-way comparison
harness.
"""
from __future__ import annotations

import glob
import json
import os
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.dataset.schema import NormalizedService

_KB_FILES = {"coords.json", "customs_rules.json", "incoterms.json", "transfer_rules.json"}

_lock = threading.Lock()
_services: list[NormalizedService] | None = None
_coords: dict[str, list] = {}
_nodes: list[dict[str, Any]] | None = None

# Korean display names for the location codes that appear in the ver6
# dataset. Anything not listed here just falls back to its location code
# (ported from glovis_scenario/engine.py::NAME_KO).
NAME_KO = {
    "KRUSN": "울산", "KRPUS": "부산", "KRINC": "인천", "KRHWA": "화성",
    "KRGJU": "광주", "KRSEL": "서울", "KRICH": "인천", "KRPTK": "평택",
    "CNSHA": "상하이", "CNNGB": "닝보", "CNTAO": "칭다오",
    "JPYOK": "요코하마", "JPNGO": "나고야", "SGSIN": "싱가포르",
    "NLRTM": "로테르담", "DEBRV": "브레머하펜", "DEHAM": "함부르크",
    "BEANR": "안트베르펜", "BEZEE": "제브뤼헤", "FRLEH": "르아브르",
    "ESVLC": "발렌시아", "ITGOA": "제노바", "PLGDN": "그단스크",
    "SEGOT": "예테보리", "SIKOP": "코페르", "GBSOU": "사우샘프턴",
    "DEMUC": "뮌헨", "DESTR": "슈투트가르트", "DEFRA": "프랑크푸르트",
    "DEKOL": "쾰른", "DEDUI": "뒤스부르크", "DELEI": "라이프치히",
    "ATVIE": "빈", "CZPRG": "프라하", "PLWAW": "바르샤바",
    "ITMIL": "밀라노", "ESMAD": "마드리드", "FRPAR": "파리", "HUBUD": "부다페스트",
}


def _f(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _node_code(end: dict) -> str:
    return end.get("location_id") or end.get("node_id")


def _vehicle_cost_usd(s: dict):
    p = s.get("pricing", {})
    model = p.get("pricing_model")
    if "cost_usd_per_vehicle_all_in" in p:
        return p["cost_usd_per_vehicle_all_in"]
    if model == "per_vehicle":
        return p.get("rate_per_vehicle")
    if model == "per_wagon":
        rpw = p.get("rate_per_wagon")
        return rpw / 8 if rpw else None
    if model == "per_transporter":
        rate = p.get("rate_per_transporter")
        fleet = s.get("fleet") or [{}]
        cap = fleet[0].get("vehicle_capacity", 5)
        return rate / cap if rate else None
    if model == "chargeable_weight":
        rate = p.get("rate_per_kg")
        return rate * 1700 if rate else None
    return None


def _transit_total_days(s: dict):
    sch = s.get("schedule", {})
    if "total_days_with_wait" in sch:
        return sch.get("transit_days", 0.0), sch["total_days_with_wait"] - sch.get("transit_days", 0.0), sch["total_days_with_wait"]
    transit_h = sch.get("transit_hours")
    transit_d = sch.get("transit_days", (transit_h / 24) if transit_h is not None else None)
    wait_d = sch.get("average_wait_days")
    if wait_d is None and "average_wait_hours" in sch:
        wait_d = sch["average_wait_hours"] / 24
    if transit_d is None:
        return None, None, None
    wait_d = wait_d or 0.0
    return transit_d, wait_d, transit_d + wait_d


def _capacity(s: dict):
    cap = s.get("capacity", {})
    for k in ("available_vehicle_slots", "available_weight_kg"):
        if k in cap:
            return cap[k]
    fleet = s.get("fleet")
    if fleet:
        return sum(f.get("available_count", 0) * f.get("vehicle_capacity", 1) for f in fleet)
    return None


def _reliability(s: dict) -> float:
    return s.get("performance", {}).get("on_time_rate", 0.8)


def _co2(s: dict):
    return s.get("environment", {}).get("co2_kg_per_vehicle")


def _cargo_ok_vehicle(s: dict) -> bool:
    allowed = s.get("cargo_conditions", {}).get("allowed_cargo_types", [])
    if "carries_finished_vehicle" in s:
        return bool(s["carries_finished_vehicle"])
    return "FINISHED_VEHICLE" in allowed


def _load_services(base: Path) -> list[NormalizedService]:
    out: list[NormalizedService] = []
    for fp in sorted(glob.glob(os.path.join(str(base), "*.json"))):
        name = os.path.basename(fp)
        if name in _KB_FILES:
            continue
        d = json.load(open(fp, encoding="utf-8"))
        if "services" not in d:
            continue
        carrier = d.get("carrier", {})
        for s in d["services"]:
            if not _cargo_ok_vehicle(s):
                continue
            cost = _vehicle_cost_usd(s)
            transit_d, wait_d, total_d = _transit_total_days(s)
            if cost is None or total_d is None:
                continue
            out.append(NormalizedService(
                service_id=s.get("service_id", ""),
                carrier_id=carrier.get("carrier_id", "?"),
                carrier_name=carrier.get("carrier_name", "?"),
                mode=carrier.get("group", s.get("mode", "?")),
                origin=_node_code(s["origin"]), destination=_node_code(s["destination"]),
                cost_usd=cost, cost_unit="vehicle",
                transit_days=transit_d, wait_days=wait_d, total_days=total_d,
                reliability_score=_reliability(s), co2_kg=_co2(s),
                available_capacity=_capacity(s),
                allowed_vehicle_types=s.get("cargo_conditions", {}).get("allowed_vehicle_types") or None,
                carrier_role=carrier.get("role"),
                source_dataset="ver6", raw=s,
            ))
    return out


def _load_coords(base: Path) -> dict[str, list]:
    fp = base / "coords.json"
    if not fp.is_file():
        return {}
    return json.load(open(fp, encoding="utf-8"))


def _ensure_loaded() -> None:
    global _services, _coords, _nodes
    if _services is not None:
        return
    with _lock:
        if _services is not None:
            return
        base = settings.dataset_dir
        if not base.is_dir():
            raise RuntimeError(f"dataset 폴더를 찾을 수 없습니다: {base}")
        _services = _load_services(base)
        _coords = _load_coords(base)
        _nodes = _build_nodes(_services, _coords)


def _build_nodes(services: list[NormalizedService], coords: dict[str, list]) -> list[dict[str, Any]]:
    by_node_id: dict[str, dict[str, Any]] = {}
    for s in services:
        for end_key in ("origin", "destination"):
            raw_end = s.raw.get(end_key, {})
            node_id = raw_end.get("node_id") or getattr(s, end_key)
            location_id = raw_end.get("location_id") or getattr(s, end_key)
            node_type = raw_end.get("node_type")
            country = raw_end.get("country")
            existing = by_node_id.get(node_id)
            if existing is None:
                by_node_id[node_id] = {
                    "node_id": node_id,
                    "location_id": location_id,
                    "node_type": node_type,
                    "country": country,
                }
            elif not existing.get("country") and country:
                existing["country"] = country

    out = []
    for node_id, info in by_node_id.items():
        coord = coords.get(info["location_id"])
        out.append({
            "node_id": node_id,
            "location_id": info["location_id"],
            "name": NAME_KO.get(info["location_id"], info["location_id"]),
            "node_type": info["node_type"],
            "country": info["country"],
            "latitude": coord[0] if coord else None,
            "longitude": coord[1] if coord else None,
        })
    out.sort(key=lambda n: n["node_id"])
    return out


def get_services() -> list[NormalizedService]:
    _ensure_loaded()
    assert _services is not None
    return _services


def get_nodes() -> list[dict[str, Any]]:
    _ensure_loaded()
    assert _nodes is not None
    return _nodes


def display_name(location_id: str) -> str:
    _ensure_loaded()
    return NAME_KO.get(location_id, location_id)
