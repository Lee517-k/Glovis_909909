"""Layer-1 screening: run route search over all 6 candidate datasets and
print a comparison table (coverage / trade-off sensitivity / integrity).

No LLM, no CarrierAgent — pure data-quality triage before writing agent code.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from adapters import LOADERS
from route_search import find_routes, reachable_destinations

DATA_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pick_test_pair(services):
    kr_origins = sorted({s.origin for s in services if s.origin.startswith("KR")})
    for origin in kr_origins:
        reach = reachable_destinations(services, origin, max_hops=3)
        de_dest = sorted(d for d in reach if d.startswith("DE") and d != origin)
        if de_dest:
            return origin, de_dest[0]
    # fallback: any KR origin -> any non-KR reachable node
    for origin in kr_origins:
        reach = reachable_destinations(services, origin, max_hops=3)
        other = sorted(d for d in reach if not d.startswith("KR") and d != origin)
        if other:
            return origin, other[0]
    return None, None


def integrity_issues(services):
    bad = 0
    for s in services:
        if s.cost_usd <= 0 or s.total_days <= 0:
            bad += 1
        if not (0 <= s.reliability_score <= 1):
            bad += 1
    return bad


def trade_off_diversity(routes):
    if len(routes) < 2:
        return False
    by_cost = min(routes, key=lambda r: r.total_cost_usd)
    by_days = min(routes, key=lambda r: r.total_days)
    by_co2 = min(routes, key=lambda r: r.total_co2_kg)
    keys = {id(by_cost), id(by_days), id(by_co2)}
    return len(keys) > 1


def _screen_pool(services):
    """Run the pair-pick + route-search + trade-off check on one self-contained pool
    of services (either a whole dataset, or a single Set for v1/v2)."""
    origin, dest = pick_test_pair(services)
    if origin is None:
        return None
    routes = find_routes(services, origin, dest, max_hops=3)
    if not routes:
        return {"origin": origin, "dest": dest, "n_routes": 0, "best_cost": float("nan"),
                "best_days": float("nan"), "diverse": False}
    return {
        "origin": origin, "dest": dest, "n_routes": len(routes),
        "best_cost": min(r.total_cost_usd for r in routes),
        "best_days": min(r.total_days for r in routes),
        "diverse": trade_off_diversity(routes),
    }


def main(dataset_names=("ver6",)):
    """Defaults to just ver6 — the other LOADERS entries are retired
    datasets whose folders no longer exist on disk (see adapters.py).
    Pass e.g. main(LOADERS.keys()) to attempt all of them anyway."""
    print(f"{'dataset':<18} {'#services':>10} {'test O-D':>16} {'#routes':>8} "
          f"{'best $':>9} {'best days':>10} {'trade-off?':>11} {'bad rows':>9}")
    print("-" * 100)
    for name in dataset_names:
        loader = LOADERS[name]
        try:
            services = loader(DATA_ROOT)
        except Exception as e:
            print(f"{name:<18} FAILED TO LOAD: {e}")
            continue

        bad = integrity_issues(services)
        groups = sorted({s.scenario_group for s in services if s.scenario_group})

        if groups:
            # v1_final / v2_fixed: Set1/Set2/Set3 are independent markets —
            # never chain legs across groups, screen each separately and sum.
            results = []
            for g in groups:
                pool = [s for s in services if s.scenario_group == g]
                r = _screen_pool(pool)
                if r:
                    r["group"] = g
                    results.append(r)
            if not results:
                print(f"{name:<18} {len(services):>10} {'no KR->DE path':>16}")
                continue
            total_routes = sum(r["n_routes"] for r in results)
            best_cost = min(r["best_cost"] for r in results)
            best_days = min(r["best_days"] for r in results)
            diverse = any(r["diverse"] for r in results)
            od = f"{len(results)} sets"
            print(f"{name:<18} {len(services):>10} {od:>16} {total_routes:>8} "
                  f"{best_cost:>9.0f} {best_days:>10.1f} {str(diverse):>11} {bad:>9}")
            for r in results:
                print(f"    {r['group']:<8} {r['origin']}->{r['dest']:<10} "
                      f"routes={r['n_routes']:<4} best=${r['best_cost']:.0f} / {r['best_days']:.1f}d "
                      f"diverse={r['diverse']}")
        else:
            r = _screen_pool(services)
            if r is None:
                print(f"{name:<18} {len(services):>10} {'no KR->DE path':>16}")
                continue
            od = f"{r['origin']}->{r['dest']}"
            print(f"{name:<18} {len(services):>10} {od:>16} {r['n_routes']:>8} "
                  f"{r['best_cost']:>9.0f} {r['best_days']:>10.1f} {str(r['diverse']):>11} {bad:>9}")


if __name__ == "__main__":
    main()
