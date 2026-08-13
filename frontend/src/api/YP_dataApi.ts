const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

export interface YPSummary {
  carriers: number;
  services: number;
  countries: number;
  modes: number;
  mode_counts: { mode: string; count: number }[];
}

export interface YPCapability {
  capability_id: string;
  carrier_id: string;
  carrier_name: string;
  mode: string;
  origin_name: string;
  destination_name: string;
  transit_hours: number | null;
  on_time_rate: number | null;
  validation_status: string;
}

export interface YPReliability {
  carrier_id: string;
  carrier_name: string;
  capability_count: number;
  score: number;
  verified_count: number;
  review_count: number;
  last_validated_at: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`데이터를 불러오지 못했습니다. (${response.status})`);
  return response.json() as Promise<T>;
}

export const getYPSummary = () => getJson<YPSummary>("/yp/capabilities/summary");
export const getYPCapabilities = () => getJson<{ items: YPCapability[] }>("/yp/capabilities?limit=100");
export const getYPReliability = () => getJson<{ items: YPReliability[] }>("/yp/reliability");

