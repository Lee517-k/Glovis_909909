"""Phase 2: run the real CarrierAgent + GlovisAgent (LLM-backed) over the
candidate dataset(s) and save the behavior-outcome logs.

Usage: python3 run_phase2.py [--top_k 3] [--priorities COST,TIME]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from adapters import LOADERS
from agents import GlovisAgent, GLOVIS_STANDIN_BY_DATASET
from kb import load_kb, DATASET_DIRS
from llm_client import LLMClient
from route_search import find_routes
from screen import pick_test_pair

DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(os.path.dirname(__file__), "phase2_results")


def resolve_pool_and_pair(services, forced_od=None):
    """Same as screen.py: v1_final/v2_fixed must stay within one scenario_group.

    forced_od=(origin, dest): use this exact pair for every dataset instead of
    each one auto-picking its own KR->DE nodes, so all 6 are compared on the
    identical lane. If a dataset's graph doesn't reach that pair, this reports
    it honestly (origin/dest come back None) rather than silently substituting
    a different, easier lane.
    """
    groups = sorted({s.scenario_group for s in services if s.scenario_group})
    pools = [services] if not groups else [[s for s in services if s.scenario_group == g] for g in groups]

    for pool in pools:
        if forced_od:
            o, d = forced_od
            nodes = {s.origin for s in pool} | {s.destination for s in pool}
            if o in nodes and d in nodes and find_routes(pool, o, d, max_hops=3):
                return pool, o, d
            continue
        origin, dest = pick_test_pair(pool)
        if origin:
            return pool, origin, dest
    return services, None, None


def run_single_request(dataset_name, origin, destination, priority="COST",
                        cargo="SEDAN", quantity=10, top_k=3, on_progress=None):
    """The importable entry point for a backend (FastAPI handler, worker task,
    etc.) — no argparse, no file writes, no looping over datasets. One request
    in, one result dict out. `on_progress`, if given, is called synchronously
    with a small event dict at each negotiation checkpoint (see agents.py's
    _emit call sites for the exact event shapes) — wire it to a WebSocket send
    or an SSE writer to stream status to a frontend while this runs.

    Runs synchronously and blocks for the LLM's duration (currently
    ~1-5 min on the local model) — call it from a background task/worker,
    not directly inside a request handler, or the HTTP request will hang open.
    """
    services = LOADERS[dataset_name](DATA_ROOT)
    kb = load_kb(DATA_ROOT, DATASET_DIRS[dataset_name])
    standin = GLOVIS_STANDIN_BY_DATASET.get(dataset_name)
    llm = LLMClient()
    glovis_agent = GlovisAgent(llm, kb, standin_carrier_id=standin, on_progress=on_progress)
    return glovis_agent.run(services, origin, destination, priority=priority,
                            cargo=cargo, quantity=quantity, top_k=top_k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top_k", type=int, default=3)
    ap.add_argument("--priorities", default="COST,TIME")
    ap.add_argument("--datasets", default="ver6")
    ap.add_argument("--force_od", default="KRPUS,DEHAM",
                     help="Fixed origin,destination applied to every dataset for a fair "
                          "apples-to-apples comparison. Empty string reverts to each dataset "
                          "auto-picking its own KR->DE pair.")
    args = ap.parse_args()
    priorities = args.priorities.split(",")
    dataset_names = args.datasets.split(",")
    forced_od = tuple(args.force_od.split(",")) if args.force_od else None

    os.makedirs(OUT_DIR, exist_ok=True)
    summary_rows = []

    for name in dataset_names:
        loader = LOADERS[name]
        print(f"\n=== {name} ===")
        services = loader(DATA_ROOT)
        pool, origin, dest = resolve_pool_and_pair(services, forced_od=forced_od)
        if origin is None:
            reason = f"no route for forced pair {forced_od}" if forced_od else "no KR->DE path"
            print(f"  skip: {reason}")
            with open(os.path.join(OUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
                json.dump({"_unreachable": True, "forced_od": forced_od, "reason": reason}, f, ensure_ascii=False, indent=2)
            continue
        print(f"  pool={len(pool)} services, O-D={origin}->{dest}")

        llm = LLMClient()
        kb = load_kb(DATA_ROOT, DATASET_DIRS[name])
        standin = GLOVIS_STANDIN_BY_DATASET.get(name)
        glovis_agent = GlovisAgent(llm, kb, standin_carrier_id=standin)

        results = {}
        for prio in priorities:
            t0 = time.time()
            out = glovis_agent.run(pool, origin, dest, priority=prio, top_k=args.top_k)
            out["wall_clock_this_call"] = round(time.time() - t0, 1)
            results[prio] = out
            if "error" in out:
                print(f"  [{prio}] error: {out['error']}")
                continue
            top = out["scenarios"][0]  # already sorted by this call's priority
            cost = top["agreed_cost_usd_per_vehicle"] if top["feasible"] else top["listed_cost_usd_per_vehicle"]
            days = top["agreed_total_days"] if top["feasible"] else top["listed_total_days"]
            print(f"  [{prio}] {len(out['scenarios'])} scenarios shown -> "
                  f"top pick: {top['path']} (feasible={top['feasible']}, ${cost}, {days}d)")

        with open(os.path.join(OUT_DIR, f"{name}.json"), "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2, default=str)

        # cross-priority diversity: does the top pick actually change with priority?
        top_paths = set()
        for prio, out in results.items():
            if "error" in out:
                continue
            top_paths.add(out["scenarios"][0]["path"])
        grounding = list(results.values())[0].get("grounding_check", {}) if results else {}

        summary_rows.append({
            "dataset": name, "n_pool_services": len(pool),
            "n_scenarios_per_call": args.top_k,
            "top_pick_changes_with_priority": len(top_paths) > 1,
            "grounded_leg_quotes": grounding.get("grounded"),
            "hallucinated_leg_quotes": grounding.get("hallucinated"),
            "llm_calls_total": llm.total_calls, "tokens_total": llm.total_tokens,
            "wall_clock_sec": round(llm.total_seconds, 1),
        })

    print("\n\n=== PHASE 2 SUMMARY ===")
    print(f"{'dataset':<14} {'pool':>6} {'prio_changes_pick':>18} {'grounded':>9} {'halluc':>7} "
          f"{'llm_calls':>10} {'tokens':>8} {'sec':>7}")
    for r in summary_rows:
        print(f"{r['dataset']:<14} {r['n_pool_services']:>6} "
              f"{str(r['top_pick_changes_with_priority']):>18} {str(r['grounded_leg_quotes']):>9} "
              f"{str(r['hallucinated_leg_quotes']):>7} {r['llm_calls_total']:>10} "
              f"{r['tokens_total']:>8} {r['wall_clock_sec']:>7}")

    with open(os.path.join(OUT_DIR, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_rows, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
