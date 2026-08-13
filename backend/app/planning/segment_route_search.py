from __future__ import annotations

from app.agents.infrastructure.port_infrastructure_agent import PortInfrastructureAgent
from app.dataset.node_registry import NodeRegistry
from app.domain.enums import DEFAULT_COLOCATED_TRANSFER_HOURS, TransportMode
from app.domain.models import CargoInput
from app.planning.carbon import cargo_weight_ton, grade_from_co2_per_ton, segment_co2_kg
from app.planning.graph_builder import SegmentGraph
from app.planning.types import RouteCandidate, RouteLeg, SegmentProposal

MAX_DEPTH = 4
MAX_RESULTS = 60


def _port_correction(
    segment: SegmentProposal, port_agent: PortInfrastructureAgent, cargo: CargoInput
) -> tuple[float, float, list[str]]:
    if segment.mode != TransportMode.SEA:
        return 0.0, 0.0, []
    extra_hours = 0.0
    extra_cost = 0.0
    notes: list[str] = []
    for node_id in (segment.origin_node_id, segment.destination_node_id):
        port = port_agent.get_port(node_id)
        if not port:
            continue
        extra_hours += port_agent.processing_hours(port, cargo.cargo_type)
        extra_cost += port_agent.handling_cost(port, cargo.cargo_type, cargo.quantity)
        reason = port_agent.risk_reason(port)
        if reason:
            notes.append(reason)
    return extra_hours, extra_cost, notes


def _port_risk_bump(segment: SegmentProposal, port_agent: PortInfrastructureAgent) -> float:
    if segment.mode != TransportMode.SEA:
        return 0.0
    bump = 0.0
    for node_id in (segment.origin_node_id, segment.destination_node_id):
        port = port_agent.get_port(node_id)
        if port:
            bump = max(bump, port_agent.congestion_risk(port))
    return bump


def _departure_points(node_id: str, nodes: NodeRegistry) -> list[tuple[str, float]]:
    points = [(node_id, 0.0)]
    location_id = nodes.location_of(node_id)
    if location_id:
        for alt in nodes.nodes_at_location(location_id):
            if alt != node_id:
                points.append((alt, DEFAULT_COLOCATED_TRANSFER_HOURS))
    return points


def find_routes(
    graph: SegmentGraph,
    nodes: NodeRegistry,
    port_agent: PortInfrastructureAgent,
    cargo: CargoInput,
    origin_node_id: str,
    destination_node_id: str,
) -> list[RouteCandidate]:
    results: list[RouteCandidate] = []
    weight_ton = cargo_weight_ton(cargo)

    def finalize(legs: list[RouteLeg]) -> RouteCandidate:
        total_carrier_cost = sum(l.segment.cost_usd for l in legs)
        total_infra_cost = sum(l.infra_cost_usd for l in legs)
        total_carrier_hours = sum(l.segment.duration_hours for l in legs)
        total_infra_hours = sum(l.infra_delay_hours for l in legs)
        segment_risks = [l.segment.risk_score for l in legs]
        route_risk = 0.7 * max(segment_risks) + 0.3 * (sum(segment_risks) / len(segment_risks))
        reliability = 1.0
        for l in legs:
            reliability *= l.segment.reliability_score
        co2 = sum(segment_co2_kg(l.segment, cargo) for l in legs)
        return RouteCandidate(
            legs=legs,
            total_carrier_cost=round(total_carrier_cost, 2),
            total_infra_cost=round(total_infra_cost, 2),
            total_carrier_hours=round(total_carrier_hours, 2),
            total_infra_hours=round(total_infra_hours, 2),
            total_risk_score=round(min(route_risk, 100.0), 1),
            reliability_score=round(reliability, 4),
            transfer_count=max(len(legs) - 1, 0),
            estimated_co2_kg=round(co2, 1),
            environment_grade=grade_from_co2_per_ton(co2, weight_ton),
        )

    def dfs(current_node: str, legs: list[RouteLeg], visited: set[str]) -> None:
        if len(results) >= MAX_RESULTS:
            return
        if current_node == destination_node_id and legs:
            results.append(finalize(legs))
            return
        if len(legs) >= MAX_DEPTH:
            return

        for departure_node, transfer_hours in _departure_points(current_node, nodes):
            for segment in graph.segments_from(departure_node):
                if segment.destination_node_id in visited:
                    continue
                infra_hours, infra_cost, notes = _port_correction(segment, port_agent, cargo)
                port_risk = _port_risk_bump(segment, port_agent)
                effective_segment = segment
                if port_risk > segment.risk_score:
                    effective_segment = _with_risk(segment, port_risk)
                leg = RouteLeg(
                    segment=effective_segment,
                    infra_delay_hours=transfer_hours + infra_hours,
                    infra_cost_usd=infra_cost,
                    infra_risk_notes=notes,
                )
                dfs(
                    segment.destination_node_id,
                    legs + [leg],
                    visited | {segment.destination_node_id},
                )

    dfs(origin_node_id, [], {origin_node_id})
    return _dedupe(results)


def _with_risk(segment: SegmentProposal, risk: float) -> SegmentProposal:
    import dataclasses

    return dataclasses.replace(segment, risk_score=round(risk, 1))


def _dedupe(routes: list[RouteCandidate]) -> list[RouteCandidate]:
    best: dict[tuple, RouteCandidate] = {}
    for route in routes:
        key = tuple((l.segment.service_id, l.segment.origin_node_id, l.segment.destination_node_id) for l in route.legs)
        existing = best.get(key)
        if existing is None or route.total_cost < existing.total_cost:
            best[key] = route
    return list(best.values())
