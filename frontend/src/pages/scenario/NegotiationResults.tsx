import { useMemo, useState } from "react";
import { Badge, Chip, type Mode, usd, n } from "../../lib/YP_ui";
import { WorldMap } from "../../components/WorldMap";
import { propMap, type ProposalRouteForMap } from "../../lib/maps";
import { colorFor } from "./helpers";
import type { Axis, NegotiationResult, RouteOption, SavedScenario } from "../../types/negotiation";

const AXIS_LABEL: Record<Axis, string> = { COST: "비용", TIME: "시간", CO2: "탄소", RELIABILITY: "신뢰도", BALANCED: "균형" };
const AXES: Axis[] = ["COST", "TIME", "CO2", "RELIABILITY"];

// 부산~유럽 항로가 다 들어오는 고정 뷰포트 (기존 ProviderViewer와 동일한 값).
const MAP_BOUNDS: [number, number, number, number] = [-15, 140, 55, 20];

type SaveState = { kind: "saving" } | { kind: "saved"; scenarioId: string } | { kind: "error"; message: string };
type ViewMode = "map" | "list";

export function NegotiationResults({
  result,
  selectedId,
  onSelect,
  etd,
  onEtdChange,
  onSave,
  onOpenTrace,
  onNavigateToTracking,
}: {
  result: NegotiationResult;
  selectedId: string | null;
  onSelect: (id: string) => void;
  etd: string;
  onEtdChange: (etd: string) => void;
  onSave: (routeId: string, isFavorite: boolean) => Promise<SavedScenario>;
  onOpenTrace: (route: RouteOption) => void;
  onNavigateToTracking: (scenarioId: string) => void;
}) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("map");
  // 두 액션은 완전히 독립이다 — 북마크(제안서 보관함)와 트래킹 등록은
  // 서로 다른 scenario_id로 각각 저장되고, 하나를 눌러도 다른 쪽 상태는 안 바뀐다.
  const [bookmarkStates, setBookmarkStates] = useState<Record<string, SaveState>>({});
  const [selectStates, setSelectStates] = useState<Record<string, SaveState>>({});
  const { routes, recommendation_sets, negotiation } = result;

  const mapRoutes: ProposalRouteForMap[] = useMemo(
    () =>
      routes.map((r, i) => ({
        id: r.route_id,
        color: colorFor(i),
        legs: r.legs.map((l) => [l.origin_node_id, l.destination_node_id, 0.12] as [string, string, number]),
      })),
    [routes]
  );

  // "제안서 보관함에 저장" = 북마크. 팝업/이동 없음, 보관함 목록에 추가된다.
  async function handleBookmark(routeId: string) {
    setBookmarkStates((s) => ({ ...s, [routeId]: { kind: "saving" } }));
    try {
      const saved = await onSave(routeId, true);
      setBookmarkStates((s) => ({ ...s, [routeId]: { kind: "saved", scenarioId: saved.scenario_id } }));
    } catch (e) {
      setBookmarkStates((s) => ({ ...s, [routeId]: { kind: "error", message: e instanceof Error ? e.message : "저장 실패" } }));
    }
  }

  // "이 경로 선택" = 화면 하이라이트 + 트래킹용 등록(SQLite, 보관함과는 별개).
  // 저장되면 팝업으로 물어보고, 예를 누르면 운송 추적 화면으로 넘어간다.
  async function handleSelectAndRegister(routeId: string) {
    onSelect(routeId);
    setSelectStates((s) => ({ ...s, [routeId]: { kind: "saving" } }));
    try {
      const saved = await onSave(routeId, false);
      setSelectStates((s) => ({ ...s, [routeId]: { kind: "saved", scenarioId: saved.scenario_id } }));
      const goTracking = window.confirm(`운송 일정이 저장됐습니다 (${saved.scenario_id}).\n운송 추적 화면으로 이동할까요?`);
      if (goTracking) onNavigateToTracking(saved.scenario_id);
    } catch (e) {
      setSelectStates((s) => ({ ...s, [routeId]: { kind: "error", message: e instanceof Error ? e.message : "저장 실패" } }));
    }
  }

  const selected = routes.find((r) => r.route_id === selectedId) ?? routes[0];
  const others = routes.filter((r) => r.route_id !== selected?.route_id);

  function renderCard(route: RouteOption, index: number) {
    const expanded = expandedId === route.route_id;
    const isSelected = selectedId === route.route_id;
    return (
      <section className="card" key={route.route_id} style={{ borderColor: isSelected ? "var(--blue-line)" : undefined }}>
        <div className="card-hd">
          <div>
            <h4 style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 9, height: 9, borderRadius: 3, background: colorFor(index), flex: "none" }} />
              {route.label}
              {isSelected && <Badge tone="blue">선택됨</Badge>}
              {!route.feasible && <Badge tone="danger">배차 불가 구간 포함</Badge>}
            </h4>
            <p>
              {route.modes.map((m, i) => (
                <span key={i}>
                  {i > 0 && " · "}
                  <Chip mode={m as Mode} />
                </span>
              ))}
              {"  ·  경유 " + route.metrics.transfers + "회 · 자사운송 " + route.legs_self_operated + "/" + route.legs.length + "구간"}
            </p>
          </div>
          <div className="spacer" />
          <SaveButton
            state={bookmarkStates[route.route_id]}
            onClick={() => handleBookmark(route.route_id)}
            idleLabel="보관함 저장"
            idleIcon="ti-bookmark"
            busyLabel="저장 중"
            savedLabel="저장됨"
          />
          <SaveButton
            state={selectStates[route.route_id]}
            onClick={() => handleSelectAndRegister(route.route_id)}
            idleLabel="경로 선택"
            idleIcon="ti-target-arrow"
            idleTone="blue"
            busyLabel="등록 중"
            savedLabel="등록됨"
          />
        </div>
        <div className="card-bd" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 10, marginBottom: 10 }}>
          <Metric label="대당 비용" value={usd(route.metrics.cost_usd_per_vehicle)} />
          <Metric label="선적 총액" value={usd(route.metrics.shipment_cost_usd)} />
          <Metric label="총 소요일" value={`${route.metrics.total_days}일`} />
          <Metric label="대당 CO2" value={`${n(route.metrics.co2_kg_per_vehicle)}kg`} />
          <Metric label="정시율" value={`${Math.round(route.metrics.reliability * 100)}%`} />
        </div>
        <div className="card-bd" style={{ paddingTop: 0 }}>
          <button className="btn sm" onClick={() => setExpandedId(expanded ? null : route.route_id)}>
            <i className={`ti ${expanded ? "ti-chevron-up" : "ti-chevron-down"}`} />
            구간 {route.legs.length}개 · 상세 {expanded ? "접기" : "펼치기"}
          </button>
          {expanded && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {route.legs.map((leg) => (
                <div
                  key={leg.service_id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    fontSize: 12.5,
                    padding: "8px 10px",
                    border: "1px solid var(--line)",
                    borderRadius: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <span style={{ width: 22, textAlign: "center", color: "var(--muted)" }}>{leg.sequence}</span>
                  <Chip mode={leg.mode as Mode} />
                  <b>{leg.carrier_name}</b>
                  <span style={{ color: "var(--muted)" }}>
                    {leg.origin} → {leg.destination}
                  </span>
                  <span>{usd(leg.listed_cost_usd_per_vehicle)}/대</span>
                  <span>{leg.days}일</span>
                  <span>{n(leg.co2_kg_per_vehicle)}kg CO2</span>
                  <span>정시 {Math.round(leg.reliability * 100)}%</span>
                  {leg.self_operated ? (
                    <Badge tone="gray" icon="ti-building-warehouse">
                      자사 배차
                    </Badge>
                  ) : (
                    <Badge tone="blue" icon="ti-file-invoice">
                      게시가 적용
                    </Badge>
                  )}
                </div>
              ))}
              <button className="btn sm" onClick={() => onOpenTrace(route)}>
                <i className="ti ti-list-details" />
                구간별 산정 근거 보기
              </button>
            </div>
          )}
        </div>
      </section>
    );
  }

  return (
    <>
      <section className="card" style={{ marginBottom: 14 }}>
        <div className="card-hd">
          <div>
            <h4>축별 추천</h4>
            <p>경로 탐색 결과를 축(운임·시간·탄소·신뢰도)별로 규칙 기반으로 재정렬했습니다</p>
          </div>
        </div>
        <div className="card-bd" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 10 }}>
          {AXES.map((axis) => {
            const set = recommendation_sets[axis];
            if (!set) return null;
            const route = routes.find((r) => r.route_id === set.recommended_route_id);
            const active = set.recommended_route_id === selectedId;
            return (
              <button
                key={axis}
                onClick={() => onSelect(set.recommended_route_id)}
                style={{
                  textAlign: "left",
                  border: `1px solid ${active ? "var(--blue-line)" : "var(--line)"}`,
                  background: active ? "var(--blue-bg)" : "var(--panel)",
                  borderRadius: 10,
                  padding: 12,
                  cursor: "pointer",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <span style={{ fontWeight: 800, fontSize: 12.5 }}>{AXIS_LABEL[axis]} 우선</span>
                  <Badge tone="gray" icon="ti-calculator">
                    규칙 기반
                  </Badge>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{route?.label ?? set.recommended_route_id}</div>
                <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.5 }}>{set.summary}</div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="card" style={{ marginBottom: 14, padding: "10px 16px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 12.5 }}>
          <i className="ti ti-calendar-event" />
          <label htmlFor="etd-input">
            <b>출발예정일(ETD)</b>
          </label>
          <input
            id="etd-input"
            type="datetime-local"
            value={etd}
            onChange={(e) => onEtdChange(e.target.value)}
            style={{
              width: 200,
              border: "1px solid var(--line)",
              borderRadius: 8,
              padding: "6px 10px",
              font: "inherit",
              color: "inherit",
              background: "#fff",
            }}
          />
          <span style={{ color: "var(--muted)" }}>
            "제안서 보관함에 저장"과 "이 경로 선택" 둘 다 이 날짜 기준으로 저장되지만 서로 별개의 기록입니다 — 북마크는 보관함에만
            쌓이고, 경로 선택은 운송 추적으로 넘어갑니다.
          </span>
        </div>
      </section>

      <div className="card" id="viewerCard" style={{ marginBottom: 14 }}>
        <div className="card-hd">
          <div>
            <h4>운송사 제안 뷰어</h4>
            <p>{viewMode === "map" ? "지도에서 경로를 클릭하면 좌측 제안서가 바뀝니다" : "제안 카드를 전부 펼쳐서 비교합니다"}</p>
          </div>
          <div className="spacer" />
          <div className="toggle">
            <button className={viewMode === "map" ? "active" : ""} onClick={() => setViewMode("map")}>
              MAP
            </button>
            <button className={viewMode === "list" ? "active" : ""} onClick={() => setViewMode("list")}>
              LIST
            </button>
          </div>
        </div>
        <div className="card-bd">
          {viewMode === "map" ? (
            <div className="viewer">
              <div className="plist">
                {selected && renderCard(selected, routes.indexOf(selected))}
                {others.length > 0 && (
                  <div className="sectlabel" style={{ margin: "2px 2px 0" }}>
                    다른 제안 보기
                  </div>
                )}
                {others.map((r) => {
                  const idx = routes.indexOf(r);
                  return (
                    <div className="propcard" key={r.route_id} style={{ padding: "11px 13px", cursor: "pointer" }} onClick={() => onSelect(r.route_id)}>
                      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                        <span style={{ width: 9, height: 9, borderRadius: 3, background: colorFor(idx), flex: "none" }} />
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 12.5, fontWeight: 700, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r.label}</div>
                          <div style={{ fontSize: 11, color: "var(--faint)" }}>
                            {usd(r.metrics.cost_usd_per_vehicle)}/대 · {r.metrics.total_days}일
                          </div>
                        </div>
                        <i className="ti ti-chevron-right" style={{ color: "var(--faint)" }} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="mapwrap">
                <WorldMap svg={propMap(mapRoutes, selected?.route_id ?? "", MAP_BOUNDS)} />
                <div className="maplegend">
                  {routes.map((r, i) => (
                    <span key={r.route_id} className="legpill" style={{ opacity: r.route_id === selected?.route_id ? 1 : 0.6 }}>
                      <i style={{ width: 8, height: 8, borderRadius: 3, background: colorFor(i), display: "inline-block", marginRight: 5 }} />
                      {r.label}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>{routes.map((route, i) => renderCard(route, i))}</div>
          )}
        </div>
      </div>
    </>
  );
}

function SaveButton({
  state,
  onClick,
  idleLabel,
  idleIcon,
  idleTone,
  busyLabel,
  savedLabel,
}: {
  state: SaveState | undefined;
  onClick: () => void;
  idleLabel: string;
  idleIcon: string;
  idleTone?: "blue";
  busyLabel: string;
  savedLabel: string;
}) {
  if (state?.kind === "saving") {
    return (
      <button className="btn sm" disabled>
        <i className="ti ti-loader-2" />
        {busyLabel}
      </button>
    );
  }
  if (state?.kind === "saved") {
    return (
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Badge tone="ok" icon="ti-database-check">
          {savedLabel} · {state.scenarioId}
        </Badge>
        <button className="btn sm ghost" onClick={onClick} title="다시 저장(덮어쓰기)">
          <i className="ti ti-refresh" />
        </button>
      </span>
    );
  }
  if (state?.kind === "error") {
    return (
      <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <Badge tone="danger" icon="ti-alert-triangle">
          {state.message}
        </Badge>
        <button className="btn sm" onClick={onClick}>
          <i className="ti ti-refresh" />
          재시도
        </button>
      </span>
    );
  }
  return (
    <button className={`btn sm ${idleTone ?? ""}`} onClick={onClick}>
      <i className={`ti ${idleIcon}`} />
      {idleLabel}
    </button>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "6px 8px", minWidth: 0 }}>
      <div style={{ fontSize: 10, color: "var(--muted)", marginBottom: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</div>
      <div style={{ fontSize: 13.5, fontWeight: 750, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{value}</div>
    </div>
  );
}
