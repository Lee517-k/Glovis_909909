"""Deterministic multi-leg route assembly — no LLM involved.

This is the "combinatorial search" half of the Coordinator described in the
conversation: given a pool of NormalizedService legs, find every way to chain
them from an origin to a destination. What comes out of find_routes() is the
list of composite transport scenarios themselves.
"""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class RouteCandidate:
    legs: list
    total_cost_usd: float
    total_days: float
    total_co2_kg: float
    reliability: float  # product of leg reliabilities

    def path_str(self):
        nodes = [self.legs[0].origin] + [l.destination for l in self.legs]
        modes = "+".join(sorted({l.mode for l in self.legs}))
        return "→".join(nodes) + f"  [{modes}]"


def vehicle_type_ok(service, vehicle_type):
    """Can this leg physically carry the requested vehicle type?

    yum_ver2_all: each row IS one specific vehicle_class (SEDAN row, SUV row, ...)
      -> must match exactly, or a route could silently splice a sedan leg to a
         HIGH_HEAVY leg for what's supposed to be one shipment.
    ver5 / yubin_ver4 / v3: one flat-priced service lists a SET of vehicle
      types it accepts -> requested type must be in that set.
    Datasets with neither field (v1_final/v2_fixed/v3 cbm-based legs) aren't
    vehicle-typed at all -> no filter applies.
    """
    if vehicle_type is None:
        return True
    if service.vehicle_class is not None:
        return service.vehicle_class == vehicle_type
    if service.allowed_vehicle_types is not None:
        return vehicle_type in service.allowed_vehicle_types
    return True


def find_routes(services, origin, destination, max_hops=3, max_routes=500, vehicle_type=None):
    """Hop-count-ordered (BFS-by-depth) search — deliberately NOT plain DFS.

    A depth-first walk with a single global `max_routes` cap can starve out
    short/direct routes entirely: if the first edge out of `origin` leads into
    a big hub with a huge fan-out (e.g. Rotterdam), DFS will exhaust the whole
    result budget deep inside that one branch before ever backtracking to try
    the origin's *other* edges — including a direct 1-hop connection that
    would otherwise be the obvious answer. Exploring hop-count 1 to completion
    before hop-count 2, etc., guarantees a direct route is never hidden behind
    longer ones purely because of edge iteration order.

    vehicle_type: if given, legs that can't carry it (wrong yum_ver2_all
    vehicle_class, or not in a ver5-style service's allowed set) are excluded
    before the graph is even built — a route can no longer splice together
    legs priced/sized for different vehicles.
    """
    if vehicle_type is not None:
        services = [s for s in services if vehicle_type_ok(s, vehicle_type)]
    edges = defaultdict(list)
    for s in services:
        edges[s.origin].append(s)

    routes = []
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


def _finalize(routes):
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


def reachable_destinations(services, origin, max_hops=3):
    """All nodes reachable from origin — used to auto-pick a KR->DE test pair per dataset."""
    edges = defaultdict(list)
    for s in services:
        edges[s.origin].append(s.destination)
    seen = {origin}
    frontier = {origin}
    for _ in range(max_hops):
        nxt = set()
        for n in frontier:
            for d in edges.get(n, []):
                if d not in seen:
                    seen.add(d)
                    nxt.add(d)
        frontier = nxt
    return seen
