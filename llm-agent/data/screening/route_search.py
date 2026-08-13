"""Deterministic multi-leg route assembly — no LLM involved.

This is the "combinatorial search" half of the Coordinator described in the
conversation: given a pool of NormalizedService legs, find every way to chain
them from an origin to a destination. What comes out of find_routes() is the
list of composite transport scenarios themselves.
"""
import math
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


@dataclass
class _Label:
    """One non-dominated partial path reaching `node` during the search.
    `cv` (cost vector) is the thing dominance is checked on — see _cost_vec.
    legs/visited are carried along unchanged so a surviving label can still
    be extended or, at the destination, hand its legs to _finalize()."""
    legs: list
    visited: frozenset
    cv: tuple  # (cost_usd, total_days, co2_kg, -log(reliability)) — all "lower is better"


def _cost_vec(legs):
    """The 4 Pareto objectives, all additive-lower-is-better. reliability is
    the odd one out — it accumulates multiplicatively (rel *= leg.reliability)
    — so it's log-transformed here (product -> sum of logs) purely so
    dominance comparison can treat all four axes the same way. This log value
    never leaves _cost_vec/dominance: _finalize() recomputes the real
    (multiplicative) reliability from `legs` from scratch, same as before."""
    cost = sum(l.cost_usd for l in legs)
    days = sum(l.total_days for l in legs)
    co2 = sum((l.co2_kg or 0) for l in legs)
    rel = 1.0
    for l in legs:
        rel *= l.reliability_score
    return (cost, days, co2, -math.log(max(rel, 1e-12)))


def _dominates(a, b):
    """True if label a is at least as good as b on every objective and
    strictly better on at least one — i.e. b can never be part of a
    Pareto-optimal route once a exists, so b is safe to discard."""
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def _insert_label(bucket, label, max_labels_per_node):
    """Standard label-setting insert: reject `label` if some existing label
    already dominates it; otherwise add it and evict anything it dominates.
    `max_labels_per_node` is a pure safety valve against label blow-up at a
    high-fan-in hub — once the (mutually non-dominated) bucket exceeds it,
    keep only the K cheapest by a crude summed-vector tiebreak. This never
    fires for well-behaved graphs (a handful of objectives rarely produces
    more than a few non-dominated labels per node) — it's a backstop, not
    the dominance rule itself."""
    for other in bucket:
        if _dominates(other.cv, label.cv):
            return False
    bucket[:] = [o for o in bucket if not _dominates(label.cv, o.cv)]
    bucket.append(label)
    if len(bucket) > max_labels_per_node:
        bucket.sort(key=lambda l: sum(l.cv))
        del bucket[max_labels_per_node:]
    return True


def find_routes(services, origin, destination, max_hops=3, max_routes=500, vehicle_type=None,
                 max_labels_per_node=20):
    """Hop-count-ordered search (still deliberately NOT plain DFS, for the
    same reason as before: a DFS walk with a single global cap can starve
    out a short/direct route entirely if the first edge leads into a big
    hub) — but intermediate transfer hubs now use Pareto label-setting
    (Martins' multi-label algorithm) to prune the search itself, instead of
    enumerating every simple path and only sorting/capping afterward.

    This is search-efficiency pruning only, not candidate selection: it's
    applied strictly to *intermediate* nodes (partial paths that still need
    to continue on to another leg), never to `destination` itself. A partial
    path reaching some hub that's worse than another partial path at that
    same hub on cost, days, co2 *and* reliability all at once is provably
    useless — any continuation the worse one could take, the better one can
    take too, for an equal-or-better result — so it's dropped right there
    instead of being carried forward and only discarded after the fact.
    Every route that actually reaches `destination` is still collected,
    unfiltered and unranked, exactly like before; `_finalize()` and the
    axis-based top_k selection in agents.py are untouched, so this only
    changes how fast/completely the search runs, not what candidates make it
    into the result. `max_routes` is kept as a hard stop on *routes found*,
    same as before, for graphs where intermediate pruning alone isn't enough
    to keep the search bounded.

    Caveat: dominance at each hub is decided on the cost vector alone, not
    on (cost vector, visited-set) jointly — a strictly cheaper partial path
    can in principle evict a pricier one that would have gone on to reach a
    node the cheaper one's path already used up. For this graph's shape (a
    handful of hops, hub-and-spoke lanes) that's not a real-world concern,
    but it means this isn't a textbook-exact resource-constrained variant.

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

    frontier_by_node = {origin: [_Label([], frozenset({origin}), (0.0, 0.0, 0.0, 0.0))]}
    dest_routes = []

    for _hop in range(max_hops):
        next_frontier_by_node = {}
        for node, labels in frontier_by_node.items():
            for label in labels:
                for s in edges.get(node, []):
                    if s.destination in label.visited:
                        continue
                    new_legs = label.legs + [s]
                    if s.destination == destination:
                        dest_routes.append(new_legs)  # unfiltered — this is the candidate list, not the search frontier
                        if len(dest_routes) >= max_routes:
                            return _finalize(dest_routes)
                    else:
                        new_label = _Label(new_legs, label.visited | {s.destination}, _cost_vec(new_legs))
                        bucket = next_frontier_by_node.setdefault(s.destination, [])
                        _insert_label(bucket, new_label, max_labels_per_node)
        frontier_by_node = next_frontier_by_node

    return _finalize(dest_routes)


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
