// Types for the scenario search API (backend/app/api/yum).
// Ported field-for-field from the reference project's types/negotiation.ts
// (which itself mirrors backend/app/yum/schemas.py + adapter.py). Field
// names are unchanged even though this backend has no LLM negotiation —
// negotiation.trace is always [] and negotiation.grounding is always zeroed
// out except for the self_operated/externally_negotiated leg counts, so the
// same shape still means something honest without an LLM behind it.

export type Axis = "COST" | "TIME" | "CO2" | "RELIABILITY" | "BALANCED";
export type CargoType = "SEDAN" | "SUV" | "EV" | "PICKUP" | "LIGHT_COMMERCIAL" | "HIGH_HEAVY";

export interface NegotiationNode {
  node_id: string;
  location_id: string;
  name: string;
  node_type?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface NegotiationRequest {
  origin: string;
  destination: string;
  vehicle_type: CargoType;
  quantity: number;
  selected_axis: Axis;
  top_k: number;
  max_transit_days?: number | null;
}

export interface NegotiationStartResponse {
  request_id: string;
  status: "PROCESSING";
}

export interface NegotiationEvent {
  stage: string;
  status?: string;
  message: string;
  [key: string]: unknown;
}

export interface RouteLeg {
  sequence: number;
  carrier_id: string;
  carrier_name: string;
  service_id: string;
  mode: string;
  self_operated: boolean;
  origin: string;
  destination: string;
  origin_node_id: string;
  destination_node_id: string;
  listed_cost_usd_per_vehicle: number;
  days: number;
  co2_kg_per_vehicle: number;
  reliability: number;
}

export interface RouteMetrics {
  cost_usd_per_vehicle: number;
  shipment_cost_usd: number;
  total_days: number;
  co2_kg_per_vehicle: number;
  shipment_co2_kg: number;
  reliability: number;
  transfers: number;
}

export interface RouteOption {
  route_id: string;
  label: string;
  path: string[];
  modes: string[];
  feasible: boolean;
  metrics: RouteMetrics;
  legs_self_operated: number;
  legs: RouteLeg[];
}

export interface RecommendationSet {
  recommended_route_id: string;
  ranked_route_ids: string[];
  summary: string;
  source: "computed";
}

export interface NegotiationTraceEntry {
  leg_service_id: string;
  carrier_id: string;
  self_operated?: boolean;
  round1_carrier?: { decision: string; reason: string; offered_price_usd?: number };
  round2_buyer?: { decision: string; reason: string };
  rounds_used?: number;
  final: {
    deal_reached: boolean;
    price_usd?: number;
    quantity?: number;
    total_days?: number;
    rounds_used: number;
    grounded: boolean;
    self_operated: boolean;
    reason?: string;
  };
}

export interface NegotiationResult {
  schema_version: string;
  request_id: string;
  status: "completed" | "no_route";
  error?: string | null;
  request: { origin: string; destination: string; cargo: string; priority: string; quantity: number; vehicle_type: string };
  search_summary: {
    candidate_routes_found: number;
    excluded_by_deadline?: number;
    routes_returned: number;
    llm_calls: number;
    elapsed_sec: number;
  };
  recommendation_sets: Partial<Record<Axis, RecommendationSet>>;
  routes: RouteOption[];
  customs: Record<string, unknown>;
  incoterm: { code: string | null; version: string };
  negotiation: {
    trace: NegotiationTraceEntry[];
    grounding: {
      total_leg_negotiations: number;
      grounded: number;
      hallucinated: number;
      deals_rejected_or_walked: number;
      legs_self_operated_by_glovis: number;
      legs_externally_negotiated: number;
    };
  };
  warnings: string[];
}

export interface SaveRoutePayload {
  route_id: string;
  etd?: string;
  scenario_name?: string;
  is_favorite?: boolean;
}

export interface SavedScenarioTracking {
  shipment_status: "PLANNED" | "IN_TRANSIT" | "COMPLETED";
  progress_percent: number;
  current_location: string;
  risk_level: string;
  on_schedule: boolean;
  eta: string;
  eta_revised: string;
}

export interface SavedScenario {
  scenario_id: string;
  scenario_name: string;
  status: "DRAFT" | "CONFIRMED" | "ACTIVE" | "CANCELLED" | "CLOSED";
  is_favorite: boolean;
  created_at: string;
  schedule: { etd: string; eta: string; total_transit_hours: number };
  metrics: RouteMetrics & { customs_days?: number };
  route: { origin_name: string; destination_name: string; path: string[]; modes: string[] };
  tracking?: SavedScenarioTracking;
  [key: string]: unknown;
}

export interface NegotiationJob {
  request_id: string;
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  progress: number;
  stage: string;
  message: string;
  events: NegotiationEvent[];
  result: NegotiationResult | null;
  error: string | null;
  started_at: string;
}
