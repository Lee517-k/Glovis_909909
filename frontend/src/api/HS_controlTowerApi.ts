// '운송 추적'/'운송사 배분' 및 그 밖의 화면이 쓰는 백엔드 클라이언트.
// 응답 필드 이름은 기존 src/data/demoData.ts 의 축약 키(id/lane/pct/st/rg/cs/n/sh …)와
// 일부러 동일하게 맞춰 두었다. 따라서 각 페이지에서 demoData import 를 아래 함수 호출로
// 바꾸기만 하면 렌더링 코드를 고치지 않고 실데이터로 전환할 수 있다.

// 기본값은 같은 origin 기준 상대 경로. vite dev server의 /api 프록시가 백엔드로 넘긴다.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

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

function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

/* ========================= 운송 추적 ========================= */

export type Tone = "ok" | "warn" | "danger" | "blue" | "gray";

export interface TrackingKpis {
  in_transit: number;
  delayed: number;
  watch: number;
  arriving_today: number;
  transship_wait: number;
  on_time_rate: number;
  cards: { icon: string; label: string; value: number; unit: string; sub: string; tone?: string | null }[];
}

export interface ShipmentRow {
  id: string;
  lane: string;
  from: string;
  to: string;
  cargo: string;
  modes: string[];
  pct: number;
  tone: string;
  loc: string;
  eta: string;
  eta_planned: string;
  eta_forecast: string;
  delay_days: number;
  st: [Tone, string];
  status: string;
  status_label: string;
  g: string;
  cii: string | null;
  co2_kg: number;
  risk_score: number;
  risk_level: string;
  carriers: string[];
  region_id: string;
  open_alerts: number;
}

export interface ShipmentListResponse {
  total: number;
  limit: number;
  offset: number;
  items: ShipmentRow[];
}

export interface ShipmentDetail extends ShipmentRow {
  shipmentId: string;
  cargoLabel: string;
  riskLabel: string;
  riskTone: Tone;
  co2Label: string;
  location: string;
  locationDetail: string;
  carrierLabel: string;
  alert: string | null;
  kv: { label: string; value: string }[];
  alerts: {
    alert_id: number;
    severity: "CRITICAL" | "WARNING" | "INFO";
    category: string;
    title: string;
    message: string;
    action_label: string;
    resolved: boolean;
    created_at: string;
  }[];
}

export interface SegmentStep {
  sequence: number;
  t: string;          // 구간 제목
  s: string;          // 부제(모드 · 운송사 또는 비고)
  p: string;          // "계획 N일"
  a: string;          // "실제 N일" | "진행중" | ""
  state: "done" | "active" | "pending";
  kind: "MOVE" | "CUSTOMS" | "HANDOVER";
  mode: string;
  icon: string;       // tabler 아이콘 이름
  carrier: string | null;
  distance_km: number | null;
  short: string;
}

export interface SegmentsResponse {
  shipment_id: string;
  steps: SegmentStep[];
  planned_days_total: number;
  actual_days_total: number;
  variance_days: number;
}

export interface RouteResponse {
  shipment_id: string;
  legs: {
    from: { node_id: string; name: string | null };
    to: { node_id: string; name: string | null };
    mode: string;
    color: string;
    state: "done" | "active" | "pending";
    progress_ratio: number;
    distance_km: number | null;
  }[];
  // 이 스키마엔 노드 좌표가 없어 프론트가 node_id로 worldmap.ts의 좌표를 직접 찾는다.
  nodes: unknown[];
  current: null;
  bbox: null;
}

export const getTrackingKpis = () => request<TrackingKpis>("/tracking/kpis");

/** 검색창 · 필터 · 정렬이 모두 이 함수를 쓴다. */
export const searchShipments = (params: {
  q?: string;
  status?: string;
  mode?: string;
  region_id?: string;
  eta_from?: string;
  eta_to?: string;
  scope?: "active" | "all" | "completed" | "planned";
  sort?: "eta" | "-eta" | "progress" | "-progress" | "risk" | "-risk" | "id" | "-id" | "name" | "-name";
  limit?: number;
  offset?: number;
} = {}) => request<ShipmentListResponse>(`/tracking/shipments${qs(params)}`);

export const getShipment = (id: string) => request<ShipmentDetail>(`/tracking/shipments/${id}`);
export const getShipmentSegments = (id: string) => request<SegmentsResponse>(`/tracking/shipments/${id}/segments`);
export const getShipmentRoute = (id: string) => request<RouteResponse>(`/tracking/shipments/${id}/route`);

/** 상세 진입 시 상세+구간+경로를 한 번에 (왕복 3회 → 1회) */
export const getShipmentOverview = (id: string) =>
  request<{ detail: ShipmentDetail; segments: SegmentsResponse; route: RouteResponse }>(
    `/tracking/shipments/${id}/overview`,
  );

export const resolveShipmentAlert = (alertId: number) =>
  request<{ alert_id: number; resolved: boolean; kpis: TrackingKpis }>(
    `/tracking/alerts/${alertId}/resolve`,
    { method: "POST" },
  );

/* ========================= 운송사 배분 ========================= */

export interface AllocationRow {
  region_id: string;
  rg: string;                        // 지역권명
  meta: string;                      // "1,284 TEU · 39%"
  hhi: string;                       // "집중도 HHI 0.26 · "
  warn: string | null;
  wt: "warn" | "danger" | null;
  cs: [string, number, string][];    // [운송사명, 비중%, 색]
  hhi_value: number;
  concentration: string;
  volume: number;
  volume_unit: string;
  volume_share_pct: number;
  top_carrier: string | null;
  top_share_pct: number | null;
}

export interface CarrierRow {
  n: string; sub: string; m: string[]; rg: string;
  v: string; sp: string; sh: number; ot: number;
  g: string; gk: string; cr: string; st: [Tone, string];
  carrier_id: string; share_pct: number; volume: number; total_volume: number;
  share_over_cap: boolean; color: string;
}

export interface HubBubble {
  k: string; r: number; m: string; t: string;
  // 이 스키마엔 노드 좌표가 없어 node_id로 프론트(worldmap.ts)가 좌표를 직접 찾는다.
  name: string; node_id: string;
  volume: number; volume_unit: string; color: string; region_id: string | null;
}

export const getRegions = () =>
  request<{ tabs: { region_id: string | null; region_name: string }[]; regions: unknown[] }>("/allocation/regions");

export const getHubs = (regionId?: string) =>
  request<{ bubbles: HubBubble[]; legend: { mode: string; label: string; color: string }[]; note: string }>(
    `/allocation/hubs${qs({ region_id: regionId })}`,
  );

export const getAllocations = (regionId?: string) =>
  request<{ allocations: AllocationRow[]; grand_total_volume: number }>(
    `/allocation/allocations${qs({ region_id: regionId })}`,
  );

export const getCarriers = (regionId?: string, mode?: string, sort?: string) =>
  request<{ total: number; items: CarrierRow[] }>(
    `/allocation/carriers${qs({ region_id: regionId, mode, sort })}`,
  );

export const getAllocationSummary = (regionId?: string) =>
  request<{
    region_count: number; carrier_count: number; total_volume: number;
    total_spend_100m: number; avg_hhi: number; max_hhi_region: string;
    risk_regions: { region_id: string; region_name: string; hhi: number; top_carrier: string; top_share_pct: number; tone: string }[];
  }>(`/allocation/summary${qs({ region_id: regionId })}`);

/** 탭 전환 시 한 번에 (지도+배분+표+요약) */
export const getAllocationOverview = (regionId?: string) =>
  request<{
    regions: Awaited<ReturnType<typeof getRegions>>;
    hubs: Awaited<ReturnType<typeof getHubs>>;
    allocations: Awaited<ReturnType<typeof getAllocations>>;
    carriers: Awaited<ReturnType<typeof getCarriers>>;
    summary: Awaited<ReturnType<typeof getAllocationSummary>>;
  }>(`/allocation/overview${qs({ region_id: regionId })}`);

/** 'CSV' 버튼 — 파일 다운로드는 브라우저에 맡긴다. */
export const carriersCsvUrl = (regionId?: string, mode?: string) =>
  `${API_BASE}/allocation/carriers.csv${qs({ region_id: regionId, mode })}`;

/* ========================= 그 외 화면 ========================= */

export const globalSearch = (q: string, limit = 8) =>
  request<{
    q: string; total: number;
    groups: { key: string; label: string; page: string; items: { id: string; title: string; sub: string; meta: string }[] }[];
  }>(`/search${qs({ q, limit })}`);

export const getOpsAlerts = () =>
  request<{
    total: number;
    counts: Record<string, number>;
    alerts: { alert_id: string; t: string; lb: string; h: string; d: string; a: string; page: string; ago: string }[];
  }>("/ops/alerts");

export const dismissOpsAlert = (id: string) =>
  request<{ alert_id: string; dismissed: boolean }>(`/ops/alerts/${id}/dismiss`, { method: "POST" });

export const getOpsOverview = () => request<Record<string, unknown>>("/ops/overview");

export const getSavedProposals = () =>
  request<{
    total: number;
    items: { id: string; t: string; cost: string; days: string; esg: string; when: string; tag: [Tone, string]; modes: string[] }[];
  }>("/proposals");

export const saveProposal = (payload: {
  proposal_id?: string; title: string; cost_amount?: number; currency?: string;
  days?: number; esg_grade?: string; tag_tone?: string; tag_label?: string; modes?: string[];
}) => request<{ proposal_id: string; saved: boolean }>("/proposals", { method: "POST", body: JSON.stringify(payload) });

export const deleteProposal = (id: string) =>
  request<{ proposal_id: string; deleted: boolean }>(`/proposals/${id}`, { method: "DELETE" });

/** 데이터 업로드 — multipart 이므로 Content-Type 은 브라우저가 정하게 둔다. */
export async function uploadRateSheet(file: File) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/uploads`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`upload failed (${res.status}): ${await res.text()}`);
  return res.json() as Promise<{
    batch_id: string; filename: string; row_count: number; column_count: number;
    auto_mapped: number; needs_review: number; skipped: number;
    mapping: { source: string; target: string; note: string; tone: string; status: string }[];
    issues: { t: string; i: string; h: string; d: string; s: string; a: string }[];
    impact: { scenario_id: string; current: string; after: string; tone: string; delta: string }[];
  }>;
}

export const commitUpload = (batchId: string) =>
  request<{ committed: boolean; batch_id: string }>(`/uploads/${batchId}/commit`, { method: "POST" });
