import type { NegotiationJob, NegotiationNode, NegotiationRequest, NegotiationStartResponse, SaveRoutePayload, SavedScenario } from "../types/negotiation";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${init?.method ?? "GET"} ${path} failed (${res.status}): ${body}`);
  }
  return res.json() as Promise<T>;
}

export async function getNegotiationNodes(): Promise<NegotiationNode[]> {
  const data = await request<{ nodes: NegotiationNode[] }>("/scenarios/yum/nodes");
  return data.nodes;
}

export async function startNegotiation(payload: NegotiationRequest): Promise<NegotiationStartResponse> {
  return request<NegotiationStartResponse>("/scenarios/yum/negotiate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getNegotiation(requestId: string): Promise<NegotiationJob> {
  return request<NegotiationJob>(`/scenarios/yum/negotiate/${requestId}`);
}

export async function saveNegotiationRoute(requestId: string, payload: SaveRoutePayload): Promise<SavedScenario> {
  return request<SavedScenario>(`/scenarios/yum/negotiate/${requestId}/save`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSavedScenarios(opts?: { favoriteOnly?: boolean }): Promise<SavedScenario[]> {
  const qs = opts?.favoriteOnly ? "?favorite=true" : "";
  const data = await request<{ scenarios: SavedScenario[] }>(`/scenarios/yum/saved${qs}`);
  return data.scenarios;
}

export async function toggleFavoriteScenario(scenarioId: string): Promise<SavedScenario> {
  return request<SavedScenario>(`/scenarios/yum/saved/${scenarioId}/favorite`, { method: "PATCH" });
}

export async function deleteSavedScenario(scenarioId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/scenarios/yum/saved/${scenarioId}`, { method: "DELETE" });
  if (!res.ok && res.status !== 404) {
    throw new Error(`DELETE /scenarios/yum/saved/${scenarioId} failed (${res.status})`);
  }
}
