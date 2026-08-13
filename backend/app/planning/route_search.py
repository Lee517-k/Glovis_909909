"""Deterministic multi-leg route assembly — no LLM involved.

Ported essentially as-is from the reference project's
llm-agent/route_search.py::find_routes. Given a pool of NormalizedService
legs, finds every way to chain them from an origin to a destination.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.dataset.schema import NormalizedService


@dataclass
class RouteCandidate:
    legs: list[NormalizedService]
    total_cost_usd: float
    total_days: float
    total_co2_kg: float
    reliability: float  # product of leg reliabilities

    def path_str(self) -> str:
        nodes = [self.legs[0].origin] + [l.destination for l in self.legs]
        modes = "+".join(sorted({l.mode for l in self.legs}))
        return "→".join(nodes) + f"  [{modes}]"


def vehicle_type_ok(service: NormalizedService, vehicle_type: str | None) -> bool:
    """Can this leg physically carry the requested vehicle type?"""
    if vehicle_type is None:
        return True
    if service.vehicle_class is not None:
        return service.vehicle_class == vehicle_type
    if service.allowed_vehicle_types is not None:
        return vehicle_type in service.allowed_vehicle_types
    return True


def find_routes(
    services: list[NormalizedService],
    origin: str,
    destination: str,
    max_hops: int = 3,
    max_routes: int = 500,
    vehicle_type: str | None = None,
) -> list[RouteCandidate]:
    """Hop-count-ordered (BFS-by-depth) search — deliberately NOT plain DFS.

    Exploring hop-count 1 to completion before hop-count 2, etc., guarantees
    a direct route is never hidden behind longer ones purely because of edge
    iteration order.
    """
    if vehicle_type is not None:
        services = [s for s in services if vehicle_type_ok(s, vehicle_type)]
    edges: dict[str, list[NormalizedService]] = defaultdict(list)
    for s in services:
        edges[s.origin].append(s)

    routes: list[list[NormalizedService]] = []
    frontier = [([], origin, frozenset({origin}))]
    for _hop in range(max_hops):
        next_frontier = []
        for path, node, visited in frontier:
            for s in edges.get(node, []):
                if s.destination in visited:
                    continue
                new_path = path + [s]
                if s.destination == destination:
                    routes.append(new_path)
                    if len(routes) >= max_routes:
                        return _finalize(routes)
                else:
                    next_frontier.append((new_path, s.destination, visited | {s.destination}))
        frontier = next_frontier

    return _finalize(routes)


def _finalize(routes: list[list[NormalizedService]]) -> list[RouteCandidate]:
    out = []
    for legs in routes:
        cost = sum(l.cost_usd for l in legs)
        days = sum(l.total_days for l in legs)
        co2 = sum((l.co2_kg or 0) for l in legs)
        rel = 1.0
        for l in legs:
            rel *= l.reliability_score
        out.append(RouteCandidate(legs, cost, days, co2, rel))
    return out
