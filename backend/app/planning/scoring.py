from __future__ import annotations

from app.domain.models import PriorityWeights
from app.planning.feasibility import within_budget, within_deadline
from app.planning.types import RouteCandidate

BUDGET_OVERAGE_PENALTY = 10.0
DEADLINE_OVERAGE_PENALTY = 15.0
BUDGET_OVERAGE_THRESHOLD = 1.05
DEADLINE_OVERAGE_THRESHOLD = 1.05


def pareto_filter(routes: list[RouteCandidate]) -> list[RouteCandidate]:
    """Drop a route dominated on cost/time/risk/carbon by another (spec section 8.4)."""

    def dominates(a: RouteCandidate, b: RouteCandidate) -> bool:
        metrics_a = (a.total_cost, a.total_hours, a.total_risk_score, a.estimated_co2_kg)
        metrics_b = (b.total_cost, b.total_hours, b.total_risk_score, b.estimated_co2_kg)
        not_worse = all(x <= y for x, y in zip(metrics_a, metrics_b))
        strictly_better = any(x < y for x, y in zip(metrics_a, metrics_b))
        return not_worse and strictly_better

    kept = []
    for i, route in enumerate(routes):
        if not any(dominates(other, route) for j, other in enumerate(routes) if j != i):
            kept.append(route)
    return kept


def _normalize_benefit(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    return [1 - (v - lo) / (hi - lo) for v in values]


def score_routes(
    routes: list[RouteCandidate],
    priority: PriorityWeights,
    max_budget_usd: float,
    max_days: float,
) -> list[tuple[RouteCandidate, float]]:
    if not routes:
        return []

    cost_benefit = _normalize_benefit([r.total_cost for r in routes])
    time_benefit = _normalize_benefit([r.total_hours for r in routes])
    risk_benefit = _normalize_benefit([r.total_risk_score for r in routes])
    reliability_values = [r.reliability_score for r in routes]
    rel_lo, rel_hi = min(reliability_values), max(reliability_values)
    reliability_benefit = (
        [1.0 for _ in routes]
        if rel_hi == rel_lo
        else [(v - rel_lo) / (rel_hi - rel_lo) for v in reliability_values]
    )

    total_weight = priority.cost + priority.time + priority.reliability + priority.risk or 1.0

    scored: list[tuple[RouteCandidate, float]] = []
    for i, route in enumerate(routes):
        raw = (
            priority.cost * cost_benefit[i]
            + priority.time * time_benefit[i]
            + priority.reliability * reliability_benefit[i]
            + priority.risk * risk_benefit[i]
        )
        score = 100 * raw / total_weight

        if route.total_cost > max_budget_usd * BUDGET_OVERAGE_THRESHOLD:
            score -= BUDGET_OVERAGE_PENALTY
        if (route.total_hours / 24) > max_days * DEADLINE_OVERAGE_THRESHOLD:
            score -= DEADLINE_OVERAGE_PENALTY

        scored.append((route, round(max(score, 0.0), 1)))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def recommendation_tags(
    route: RouteCandidate,
    all_routes: list[RouteCandidate],
    is_top_score: bool,
    max_budget_usd: float,
    max_days: float,
) -> list[str]:
    tags = []
    if is_top_score:
        tags.append("BEST_BALANCED")
    if route.total_cost == min(r.total_cost for r in all_routes):
        tags.append("LOWEST_COST")
    if route.total_hours == min(r.total_hours for r in all_routes):
        tags.append("FASTEST")
    if route.total_risk_score == min(r.total_risk_score for r in all_routes):
        tags.append("LOWEST_RISK")
    if route.estimated_co2_kg == min(r.estimated_co2_kg for r in all_routes):
        tags.append("LOWEST_CARBON")
    if within_budget(route, max_budget_usd):
        tags.append("WITHIN_BUDGET")
    if within_deadline(route, max_days):
        tags.append("WITHIN_DEADLINE")
    return tags or ["CANDIDATE"]
