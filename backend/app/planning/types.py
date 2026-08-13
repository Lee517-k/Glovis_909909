from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.dataset.node_registry import NodeRegistry
from app.dataset.loader import Dataset
from app.domain.enums import TransportMode
from app.domain.models import ScenarioRequest


@dataclass
class SegmentProposal:
    """One agent's proposal for a single origin->destination leg.

    Agents never see the full route; the Coordinator is the only place that
    connects segments together (spec section 5.1 / section 6).
    """

    agent_id: str
    carrier_id: str
    carrier_name: str
    mode: TransportMode
    service_id: str
    origin_node_id: str
    destination_node_id: str
    wait_hours: float
    transit_hours: float
    cost_usd: float
    capacity_available: float
    capacity_unit: str
    risk_score: float
    reliability_score: float
    cii_grade: str = "C"
    distance_km: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_hours(self) -> float:
        return self.wait_hours + self.transit_hours


@dataclass
class AgentRunResult:
    agent_id: str
    agent_name: str
    status: str  # COMPLETED | FAILED
    segments: list[SegmentProposal]
    error: str | None = None


@dataclass
class PlanningContext:
    request: ScenarioRequest
    dataset: Dataset
    nodes: NodeRegistry


@dataclass
class RouteLeg:
    segment: SegmentProposal
    infra_delay_hours: float = 0.0
    infra_cost_usd: float = 0.0
    infra_risk_notes: list[str] = field(default_factory=list)


@dataclass
class RouteCandidate:
    legs: list[RouteLeg]
    total_carrier_cost: float
    total_infra_cost: float
    total_carrier_hours: float
    total_infra_hours: float
    total_risk_score: float
    reliability_score: float
    transfer_count: int
    estimated_co2_kg: float
    environment_grade: str

    @property
    def total_cost(self) -> float:
        return self.total_carrier_cost + self.total_infra_cost

    @property
    def total_hours(self) -> float:
        return self.total_carrier_hours + self.total_infra_hours
