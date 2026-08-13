"""Rule-based per-axis ranking of RouteOption dicts.

Ported from the reference project's backend/app/yum/adapter.py (AXIS_KEYS +
_rule_summary), with two deliberate changes now that there is no LLM layer
to negotiate/rank routes:

  1. A BALANCED axis is added — the reference only exposed COST/TIME/CO2/
     RELIABILITY as summary axes (BALANCED was only ever used as the
     *search* priority passed to GlovisAgent.run, falling back there to the
     composite key `cost_usd + total_days * 20` for any priority it didn't
     special-case). We reuse that exact composite as BALANCED's sort key so
     it stays traceable to the reference rather than inventing a new
     weighting scheme.
  2. Every axis now uses `_rule_summary()` (the reference's non-LLM
     fallback text), since there is no LLM call left to reserve axis-of-the-
     request summaries for.
"""
from __future__ import annotations

from typing import Any


def _balanced_score(route: dict[str, Any]) -> float:
    m = route["metrics"]
    return m["cost_usd_per_vehicle"] + m["total_days"] * 20


AXIS_KEYS = {
    "COST": lambda r: r["metrics"]["cost_usd_per_vehicle"],
    "TIME": lambda r: r["metrics"]["total_days"],
    "CO2": lambda r: r["metrics"]["co2_kg_per_vehicle"],
    "RELIABILITY": lambda r: -r["metrics"]["reliability"],
    "BALANCED": _balanced_score,
}

AXES = list(AXIS_KEYS.keys())


def _rule_summary(axis: str, r: dict[str, Any]) -> str:
    m = r["metrics"]
    carriers = " → ".join(dict.fromkeys(l["carrier_name"] for l in r["legs"]))
    return {
        "COST": f"{carriers} 경로가 대당 ${m['cost_usd_per_vehicle']:,.1f}로 가장 저렴합니다.",
        "TIME": f"{carriers} 경로가 {m['total_days']}일로 가장 빠릅니다.",
        "CO2": f"{carriers} 경로가 대당 {m['co2_kg_per_vehicle']:,.1f}kg으로 탄소가 가장 적습니다.",
        "RELIABILITY": f"{carriers} 경로가 정시율 {m['reliability'] * 100:.1f}%로 가장 안정적입니다.",
        "BALANCED": f"{carriers} 경로가 비용(${m['cost_usd_per_vehicle']:,.1f})과 소요일({m['total_days']}일)을 "
                    f"종합했을 때 가장 균형 잡힌 선택입니다.",
    }[axis]


def sort_routes(axis: str, routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(routes, key=AXIS_KEYS[axis])


def build_recommendation_sets(routes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Rule-based recommendation set for every axis, applied uniformly
    (COST/TIME/CO2/RELIABILITY/BALANCED) — no LLM call anywhere in here."""
    sets: dict[str, dict[str, Any]] = {}
    for axis in AXES:
        srt = sort_routes(axis, routes)
        if not srt:
            continue
        sets[axis] = {
            "recommended_route_id": srt[0]["route_id"],
            "ranked_route_ids": [r["route_id"] for r in srt],
            "summary": _rule_summary(axis, srt[0]),
            "source": "computed",
        }
    return sets
