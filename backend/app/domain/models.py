from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.domain.enums import CargoType, TransportMode


class NodeRef(BaseModel):
    node_id: str
    location_id: str
    node_name: str
    node_type: str | None = None
    country_code: str | None = None


class VehicleSpec(BaseModel):
    vehicle_type: str = "SEDAN"
    length_m: float = 4.8
    width_m: float = 1.9
    height_m: float = 1.6
    weight_kg_each: float = 1600
    operable: bool = True
    ev_battery: bool = False


class CargoInput(BaseModel):
    cargo_type: CargoType
    quantity: float
    quantity_unit: Literal["vehicle", "ton", "cbm"] = "vehicle"
    ready_date: str | None = None
    vehicle: VehicleSpec | None = None
    weight_kg: float | None = None
    volume_cbm: float | None = None


class PriorityWeights(BaseModel):
    cost: float = 0.30
    time: float = 0.25
    reliability: float = 0.25
    risk: float = 0.20


class RouteInput(BaseModel):
    origin_node_id: str
    destination_node_id: str


class ConstraintsInput(BaseModel):
    max_days: float
    max_budget_usd: float


class TradeInput(BaseModel):
    incoterm: str = "FOB"
    origin_country: str
    destination_country: str


class ScenarioRequest(BaseModel):
    cargo: CargoInput
    route: RouteInput
    constraints: ConstraintsInput
    priority: PriorityWeights = Field(default_factory=PriorityWeights)
    trade: TradeInput


class ScenarioCreateResponse(BaseModel):
    scenario_id: str
    status: str
    created_at: str


class AgentRunStatus(BaseModel):
    agent_id: str
    agent_name: str
    status: Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    candidate_count: int


class AgentLogEntry(BaseModel):
    sequence: int
    agent_id: str
    level: Literal["INFO", "WARNING", "ERROR"]
    message: str


class ScenarioStatusResponse(BaseModel):
    scenario_id: str
    status: str
    progress: int
    current_step: str
    agents: list[AgentRunStatus]
    logs: list[AgentLogEntry]


class ProposalLeg(BaseModel):
    sequence: int
    mode: TransportMode
    carrier_id: str
    carrier_name: str
    service_id: str
    origin: NodeRef
    destination: NodeRef
    cost_usd: float
    transit_hours: float
    risk_score: float


class ProposalRoute(BaseModel):
    origin_node_id: str
    destination_node_id: str
    legs: list[ProposalLeg]


class ProposalCost(BaseModel):
    currency: Literal["USD"] = "USD"
    carrier_cost: float
    infrastructure_cost: float
    customs_cost: float
    total_amount: float


class ProposalSchedule(BaseModel):
    carrier_transit_hours: float
    infrastructure_delay_hours: float
    customs_clearance_hours: float
    estimated_total_hours: float
    estimated_total_days: float


class ProposalCapacity(BaseModel):
    requested_quantity: float
    available_capacity: float
    capacity_unit: str
    feasible: bool


class RiskReason(BaseModel):
    source: str
    code: str
    message: str


class ProposalRisk(BaseModel):
    risk_score: float
    risk_level: str
    reasons: list[RiskReason]


class ProposalPerformance(BaseModel):
    reliability_score: float


class ProposalEnvironment(BaseModel):
    estimated_co2_kg: float
    grade: str


class ProposalConstraintResult(BaseModel):
    cargo_match: bool
    capacity_match: bool
    deadline_match: bool
    budget_match: bool
    eligible: bool


class ProposalTradeConditions(BaseModel):
    incoterm: str
    required_documents: list[str]
    typical_clearance_days: float


class ProposalExplanation(BaseModel):
    summary: str
    strengths: list[str]
    risks: list[str]


class Proposal(BaseModel):
    proposal_id: str
    proposal_name: str
    rank: int
    score: float
    recommendation_tags: list[str]
    route: ProposalRoute
    cost: ProposalCost
    schedule: ProposalSchedule
    capacity: ProposalCapacity
    risk: ProposalRisk
    performance: ProposalPerformance
    environment: ProposalEnvironment
    constraint_result: ProposalConstraintResult
    trade_conditions: ProposalTradeConditions
    agent_explanation: ProposalExplanation


class ScenarioResultResponse(BaseModel):
    scenario_id: str
    status: str
    request_summary: ScenarioRequest
    recommended_proposal_id: str | None
    proposals: list[Proposal]
    error: dict | None = None


class ActiveRisk(BaseModel):
    risk_id: str
    source_type: str
    source_id: str
    title: str
    severity: str
    current_location: str
    expected_impact: str
    expected_delay_hours: float


class ActiveShipment(BaseModel):
    shipment_id: str
    cargo: str
    origin: str
    destination: str
    progress_percent: float
    eta: str
    current_mode: TransportMode
    risk_level: str
    cii_grade: str
    status: str


class ResourceSummary(BaseModel):
    available_sea_services: int
    available_rail_services: int
    available_air_services: int
    available_truck_services: int


class RiskSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int


class DashboardSummary(BaseModel):
    resource_summary: ResourceSummary
    risk_summary: RiskSummary
    active_risks: list[ActiveRisk]
    active_shipments: list[ActiveShipment]
