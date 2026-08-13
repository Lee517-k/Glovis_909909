from __future__ import annotations

from app.planning.types import RouteCandidate


def within_budget(route: RouteCandidate, max_budget_usd: float) -> bool:
    return route.total_cost <= max_budget_usd


def within_deadline(route: RouteCandidate, max_days: float) -> bool:
    return (route.total_hours / 24) <= max_days
