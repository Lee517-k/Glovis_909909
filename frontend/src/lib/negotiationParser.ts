import type { Axis, CargoType, NegotiationNode } from "../types/negotiation";

// Minimal rule-based parser for the free-text box above the scenario search
// form — client-side pre-fill only; the backend always takes structured
// fields. Origin/destination are matched by scanning the text for known
// node names (from GET /api/scenarios/yum/nodes) and taking them in the
// order they appear.
export interface ParsedNegotiationRequest {
  origin?: string;
  destination?: string;
  vehicleType?: CargoType;
  quantity?: number;
  axis?: Axis;
  maxTransitDays?: number;
  pills: string[];
}

export function parseNegotiationText(text: string, nodes: NegotiationNode[]): ParsedNegotiationRequest {
  const pills: string[] = [];
  const result: ParsedNegotiationRequest = { pills };

  // Multiple node_ids can share the same display name (e.g. DEHAM seaport
  // vs DEHAM_RAIL rail terminal, both "함부르크") — keep one candidate per
  // name, preferring the node whose node_id equals its location_id (the
  // "primary" node for that place) so text matching doesn't land on an
  // arbitrary mode-specific variant with no direct route.
  const byName = new Map<string, NegotiationNode>();
  for (const node of nodes) {
    if (!node.name) continue;
    const existing = byName.get(node.name);
    const isPrimary = node.node_id === node.location_id;
    if (!existing || (isPrimary && existing.node_id !== existing.location_id)) {
      byName.set(node.name, node);
    }
  }

  const found: { node: NegotiationNode; index: number }[] = [];
  for (const node of byName.values()) {
    const index = text.indexOf(node.name);
    if (index !== -1) found.push({ node, index });
  }
  found.sort((a, b) => a.index - b.index);
  if (found.length >= 1) {
    result.origin = found[0].node.node_id;
    pills.push(`${found[0].node.name} (${found[0].node.node_id})`);
  }
  if (found.length >= 2) {
    result.destination = found[found.length - 1].node.node_id;
    pills.push(`${found[found.length - 1].node.name} (${found[found.length - 1].node.node_id})`);
  }

  const qtyMatch = text.match(/(\d+)\s*대/);
  if (qtyMatch) {
    result.quantity = Number(qtyMatch[1]);
    pills.push(`완성차 ${result.quantity}대`);
  }

  if (/SUV/i.test(text)) result.vehicleType = "SUV";
  else if (/세단|승용/.test(text)) result.vehicleType = "SEDAN";
  else if (/전기차|EV\b/i.test(text)) result.vehicleType = "EV";
  else if (/픽업/.test(text)) result.vehicleType = "PICKUP";
  else if (/상용/.test(text)) result.vehicleType = "LIGHT_COMMERCIAL";
  if (result.vehicleType) pills.push(`차종 ${result.vehicleType}`);

  if (/비용|저렴|가격/.test(text)) result.axis = "COST";
  else if (/빠르|시간|납기/.test(text)) result.axis = "TIME";
  else if (/탄소|친환경|co2/i.test(text)) result.axis = "CO2";
  else if (/신뢰|정시/.test(text)) result.axis = "RELIABILITY";
  if (result.axis) pills.push(`우선순위 ${result.axis}`);

  // "36일 미만", "35일 이내", "40일 안에" 같은 납기 하드 제약.
  const daysMatch = text.match(/(\d+)\s*일\s*(미만|이내|안에|안|내로|내)/);
  if (daysMatch) {
    result.maxTransitDays = Number(daysMatch[1]);
    pills.push(`납기 ${result.maxTransitDays}일 미만`);
  }

  return result;
}
