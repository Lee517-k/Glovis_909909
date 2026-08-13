"""Single-request entry point for the frontend transport-result schema
(see /data/frontend_transport_result.example (1).json).

Unlike run_phase2.py (which loops over multiple datasets/priorities for an
internal comparison run), this is "one request in -> one result.json out",
meant to be called by a backend handler or the CLI below. No ranking is
computed here — recommendation_sets are deliberately left out; the backend
that receives routes[]/metrics decides how to rank COST vs TIME itself.

Progress is written to a file separate from the final result (request is
still running while the result file doesn't exist yet):
  {request_id}_progress.json  -- overwritten after every negotiation
                                  checkpoint (see agents.py's _emit call sites)
  {request_id}_result.json    -- written once, at the end
"""
import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from adapters import LOADERS
from agents import GlovisAgent, GLOVIS_STANDIN_BY_DATASET
from kb import DATASET_DIRS, load_coords, load_kb
from llm_client import LLMClient

DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(__file__), "frontend_results")

SCHEMA_VERSION = "1.0.0"


class ProgressWriter:
    """Accumulates on_progress events and rewrites a standalone JSON file
    after each one, so a frontend can poll request progress before the
    final result file exists."""

    def __init__(self, path, request_id):
        self.path = path
        self.request_id = request_id
        self.events = []

    def _write(self, status):
        state = {
            "request_id": self.request_id,
            "status": status,
            "current_stage": self.events[-1] if self.events else None,
            "events": self.events,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def on_progress(self, event):
        self.events.append(event)
        self._write("running")

    def finish(self, status):
        self._write(status)


def _build_name_map(services):
    """location_code -> human name, best-effort from the raw origin/destination
    blocks every dataset service carries. coords.json has no name field."""
    names = {}
    for s in services:
        raw = s.raw or {}
        for end in ("origin", "destination"):
            node = raw.get(end)
            if isinstance(node, dict):
                code = node.get("location_id") or node.get("node_id")
                name = node.get("name")
                # some nodes are named after their own code (e.g. a bare
                # seaport entry named "KRPUS") - skip those in favor of a
                # more descriptive name (e.g. "Busan") from another service
                if code and name and name != code and code not in names:
                    names[code] = name
    return names


def _build_locations(routes, coords, name_map):
    codes = set()
    for r in routes:
        codes.update(r["path"])
    locations = {}
    for code in codes:
        lat, lon, country = coords.get(code, [None, None, code[:2]])
        locations[code] = {
            "name": name_map.get(code, code),
            "country": country,
            "latitude": lat,
            "longitude": lon,
        }
    return locations


def _route_id(scenario, used_ids):
    carriers = []
    for leg in scenario["legs"]:
        if leg["carrier_id"] not in carriers:
            carriers.append(leg["carrier_id"])
    base = "ROUTE-" + "-".join(carriers[:2])
    route_id, n = base, 1
    while route_id in used_ids:
        n += 1
        route_id = f"{base}-{n}"
    used_ids.add(route_id)
    return route_id


def _route_label(scenario):
    names = []
    for leg in scenario["legs"]:
        if leg["carrier_name"] not in names:
            names.append(leg["carrier_name"])
    if len(scenario["legs"]) == 1:
        return f"{names[0]} 직항"
    return f"{'-'.join(names)} 복합운송"


def _build_route(scenario, used_ids):
    feasible = scenario["feasible"]
    metrics = {
        "cost_usd_per_vehicle": scenario["agreed_cost_usd_per_vehicle"] if feasible
                                 else scenario["listed_cost_usd_per_vehicle"],
        "shipment_cost_usd": scenario["agreed_shipment_cost_usd"] if feasible
                              else scenario["listed_shipment_cost_usd"],
        "total_days": scenario["agreed_total_days"] if feasible else scenario["listed_total_days"],
        "co2_kg_per_vehicle": scenario["total_co2_kg"],
        "reliability": scenario["reliability"],
        "transfers": max(len(scenario["legs"]) - 1, 0),
    }
    if feasible and scenario["listed_cost_usd_per_vehicle"] != scenario["agreed_cost_usd_per_vehicle"]:
        metrics["listed_cost_usd_per_vehicle"] = scenario["listed_cost_usd_per_vehicle"]

    legs = []
    for seq, leg in enumerate(scenario["legs"], start=1):
        entry = {
            "sequence": seq, "carrier_id": leg["carrier_id"], "carrier_name": leg["carrier_name"],
            "service_id": leg["service_id"], "source_dataset": leg["source_dataset"],
            "mode": leg["mode"], "origin": leg["origin"], "destination": leg["destination"],
            "self_operated": leg["self_operated"],
            "listed_cost_usd_per_vehicle": leg["listed_cost_usd_per_vehicle"],
            "agreed_cost_usd_per_vehicle": leg["agreed_cost_usd_per_vehicle"],
            "days": leg["days"],
            "co2_kg_per_vehicle": leg["co2_kg_per_vehicle"],
            "reliability": leg["reliability"],
            "negotiation_rounds": leg["negotiation_rounds"],
            "rate_validity_type": leg.get("rate_validity_type"),
            "rate_valid_to": leg.get("rate_valid_to"),
        }
        if leg.get("contract_expiring_soon"):
            entry["contract_expiring_soon"] = True
        if leg.get("rate_stale"):
            entry["rate_stale"] = True
            entry["rate_stale_reason"] = leg.get("rate_stale_reason")
        if "available_capacity" in leg:
            entry["available_capacity"] = leg["available_capacity"]
        legs.append(entry)

    return {
        "route_id": _route_id(scenario, used_ids),
        "label": _route_label(scenario),
        "path": scenario["path_codes"],
        "modes": scenario["modes"],
        "feasible": feasible,
        "metrics": metrics,
        "quantity": {
            "requested": scenario["requested_quantity"],
            "agreed": scenario["agreed_quantity"] or 0,
            "unit": "vehicle",
        },
        "legs": legs,
    }


def run_frontend_request(dataset_name="ver6", origin="KRPUS", destination="DEHAM",
                          cargo="SEDAN", quantity=10, top_k=3,
                          priorities=("COST", "TIME"), out_dir=None, max_rounds=None,
                          save_trace=True, on_progress=None):
    out_dir = out_dir or OUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    request_id = f"REQ-{origin}-{destination}-{cargo}-{quantity}"
    progress_path = os.path.join(out_dir, f"{request_id}_progress.json")
    result_path = os.path.join(out_dir, f"{request_id}_result.json")
    trace_path = os.path.join(out_dir, f"{request_id}_trace.json")

    pw = ProgressWriter(progress_path, request_id)
    def emit(event):
        pw.on_progress(event)
        if on_progress is not None:
            on_progress(event)

    emit({"stage": "loading_data", "status": "start"})

    services = LOADERS[dataset_name](DATA_ROOT)
    kb = load_kb(DATA_ROOT, DATASET_DIRS[dataset_name])
    coords = load_coords(DATA_ROOT, DATASET_DIRS[dataset_name])
    name_map = _build_name_map(services)
    standin = GLOVIS_STANDIN_BY_DATASET.get(dataset_name)
    llm = LLMClient()

    agent = GlovisAgent(llm, kb, standin_carrier_id=standin, on_progress=emit)
    out = agent.run(services, origin, destination, priority=priorities[0],
                     extra_priorities=list(priorities[1:]), cargo=cargo,
                     quantity=quantity, top_k=top_k, max_rounds=max_rounds)

    if save_trace and "negotiation_trace" in out:
        # Every actual LLM system/user prompt + raw response, per leg per round —
        # not included in result.json (that's frontend-facing only). Written
        # separately so the prompts used in this run stay inspectable afterward.
        with open(trace_path, "w", encoding="utf-8") as f:
            json.dump(out["negotiation_trace"], f, ensure_ascii=False, indent=2)

    request_block = {
        "origin": origin, "destination": destination,
        "cargo_type": "FINISHED_VEHICLE", "vehicle_type": cargo,
        "quantity": quantity, "cost_display_basis": "shipment",
    }

    if "error" in out:
        result = {
            "schema_version": SCHEMA_VERSION, "request_id": request_id,
            "status": "failed", "partial_result": False,
            "request": request_block,
            "locations": {},
            "search_summary": {"candidate_routes_found": 0, "routes_returned": 0,
                                "source_data_version": dataset_name},
            "routes": [], "customs": {}, "incoterm": {},
            "warnings": [out["error"]],
        }
    else:
        used_ids, warnings, routes = set(), [], []
        for scenario in out["scenarios"]:
            if not scenario["feasible"]:
                warnings.append(f"{scenario['path']} 후보는 일부 구간 협상 실패로 제외되었습니다.")
                continue
            routes.append(_build_route(scenario, used_ids))

        customs = out.get("customs_used") or {}
        result = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request_id,
            "status": "completed" if routes else "failed",
            "partial_result": len(routes) < len(out["scenarios"]),
            "request": request_block,
            "locations": _build_locations(routes, coords, name_map),
            "search_summary": {
                "candidate_routes_found": out["n_candidate_routes_found"],
                "routes_returned": len(routes),
                "source_data_version": dataset_name,
            },
            "routes": routes,
            "customs": {
                "origin_country": customs.get("origin_country", origin[:2]),
                "destination_country": customs.get("destination_country", destination[:2]),
                "required": customs.get("customs_required"),
                "typical_clearance_days": customs.get("typical_clearance_days"),
                "fta_applicable": customs.get("fta_applicable"),
            },
            "incoterm": {
                "code": out.get("incoterm_used"),
                "version": (out.get("incoterm_clause") or {}).get("version", "Incoterms 2020"),
            },
            "warnings": warnings,
            "negotiation": {
                "trace": out.get("negotiation_trace", []),
                "grounding": out.get("grounding_check", {}),
            },
            "agent_metrics": out.get("cost_metrics", {}),
        }

    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    pw.finish(result["status"])
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="ver6")
    ap.add_argument("--origin", default="KRPUS")
    ap.add_argument("--destination", default="DEHAM")
    ap.add_argument("--cargo", default="SEDAN")
    ap.add_argument("--quantity", type=int, default=10)
    ap.add_argument("--top_k", type=int, default=3)
    ap.add_argument("--priorities", default="COST,TIME")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--max_rounds", type=int, default=None,
                     help="Max carrier<->buyer counter-offer round-trips per leg (default: agents.NEGOTIATION_MAX_ROUNDS_DEFAULT)")
    args = ap.parse_args()

    result = run_frontend_request(
        dataset_name=args.dataset, origin=args.origin, destination=args.destination,
        cargo=args.cargo, quantity=args.quantity, top_k=args.top_k,
        priorities=tuple(args.priorities.split(",")), out_dir=args.out_dir,
        max_rounds=args.max_rounds,
    )
    print(json.dumps({"request_id": result["request_id"], "status": result["status"],
                       "routes_returned": len(result["routes"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
