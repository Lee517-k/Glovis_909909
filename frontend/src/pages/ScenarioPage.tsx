import { useEffect, useRef, useState } from "react";
import { getNegotiation, getNegotiationNodes, saveNegotiationRoute, startNegotiation } from "../api/negotiationApi";
import type { Axis, CargoType, NegotiationJob, NegotiationNode, RouteOption, SavedScenario } from "../types/negotiation";
import { parseNegotiationText } from "../lib/negotiationParser";
import { NegotiationConsole } from "./scenario/NegotiationConsole";
import { NegotiationResults } from "./scenario/NegotiationResults";
import { NodeSearchInput } from "./scenario/NodeSearchInput";
import { mergeNodeCoords } from "../lib/worldmap";
import type { DrawerContent } from "../components/Drawer";
import "./YP_glovis_primitives.css";

const DEFAULT_TEXT = "부산에서 독일 함부르크까지 세단 10대를 비용 우선으로 운송하고 싶어. 실제 운송사들과 협상까지 맡겨줘.";

interface NegotiationForm {
  origin: string;
  destination: string;
  vehicleType: CargoType;
  quantity: number;
  axis: Axis;
  topK: number;
}

const DEFAULT_FORM: NegotiationForm = {
  origin: "KRPUS",
  destination: "DEHAM",
  vehicleType: "SEDAN",
  quantity: 10,
  axis: "COST",
  topK: 3,
};

const VEHICLE_OPTIONS: CargoType[] = ["SEDAN", "SUV", "EV", "PICKUP", "LIGHT_COMMERCIAL", "HIGH_HEAVY"];
const AXIS_OPTIONS: { value: Axis; label: string }[] = [
  { value: "COST", label: "비용 우선" },
  { value: "TIME", label: "시간 우선" },
  { value: "CO2", label: "탄소 우선" },
  { value: "RELIABILITY", label: "신뢰도 우선" },
  { value: "BALANCED", label: "균형" },
];

type Step = 1 | 2 | 3 | 4;

function defaultEtd(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().slice(0, 10);
}

// 해상 경로는 30~40일씩 걸리는 게 흔해서, 기본 납기는 출발가능일 + 45일로
// 여유 있게 잡는다 — 좁게 잡으면 기본값으로 실행했는데 바로 "납기 제약
// 불만족"이 뜨는 이상한 첫 경험이 된다.
function defaultDeadline(): string {
  const d = new Date();
  d.setDate(d.getDate() + 7 + 45);
  return d.toISOString().slice(0, 10);
}

function daysBetween(fromDate: string, toDate: string): number {
  const ms = new Date(`${toDate}T00:00:00`).getTime() - new Date(`${fromDate}T00:00:00`).getTime();
  return Math.round((ms / (1000 * 60 * 60 * 24)) * 10) / 10;
}

const EMPTY_JOB: NegotiationJob = {
  request_id: "",
  status: "PROCESSING",
  progress: 0,
  stage: "queued",
  message: "",
  events: [],
  result: null,
  error: null,
  started_at: "",
};

function buildTraceDrawer(route: RouteOption, job: NegotiationJob): DrawerContent {
  const trace = job.result?.negotiation.trace ?? [];
  const steps = route.legs.map((leg) => {
    const t = trace.find((x) => x.leg_service_id === leg.service_id);
    if (!t || leg.self_operated) {
      return {
        title: `${leg.sequence}구간 · ${leg.carrier_name}`,
        detail: ["자사(글로비스) 운송이라 협상 없이 바로 배차했습니다."],
        icon: "ti-building-warehouse",
      };
    }
    const r1 = t.round1_carrier;
    const r2 = t.round2_buyer;
    const lines = [
      r1 && `1차 제안: ${r1.decision}${r1.reason ? ` — ${r1.reason}` : ""}`,
      r2 && `2차(화주) 판단: ${r2.decision}${r2.reason ? ` — ${r2.reason}` : ""}`,
      `최종: ${t.final.deal_reached ? `타결 · $${t.final.price_usd}/대` : `결렬 (${t.final.reason ?? "사유 없음"})`}`,
    ].filter(Boolean);
    return {
      title: `${leg.sequence}구간 · ${leg.carrier_name}`,
      detail: lines.filter((line): line is string => Boolean(line)),
      icon: "ti-message-2-bolt",
      tone: t.final.deal_reached ? ("ok" as const) : ("warn" as const),
    };
  });
  return {
    title: `${route.label} · LLM 협상 로그`,
    icon: "ti-message-2-bolt",
    meta: `Route ID: ${route.route_id}<br>구간 ${route.legs.length}개 · 검증(grounding) ${job.result?.negotiation.grounding.grounded}/${job.result?.negotiation.grounding.total_leg_negotiations}`,
    steps,
  };
}

export function ScenarioPage({
  active,
  onOpenDrawer,
  onSave,
  onNavigateToTracking,
}: {
  active: boolean;
  onOpenDrawer: (c: DrawerContent) => void;
  onSave: () => void;
  onNavigateToTracking: (scenarioId: string) => void;
}) {
  const [nodes, setNodes] = useState<NegotiationNode[] | undefined>(undefined);

  useEffect(() => {
    getNegotiationNodes()
      .then(setNodes)
      .catch(() => setNodes([]));
  }, []);

  // 지도 좌표표(worldmap.ts)엔 기본 노드만 미리 박혀있어서, 백엔드가 주는
  // 실제 위경도로 채워 넣어야 나머지 노드도 결과 지도에 정확히 찍힌다.
  useEffect(() => {
    if (nodes) mergeNodeCoords(nodes.map((nd) => ({ node_id: nd.node_id, longitude: nd.longitude, latitude: nd.latitude, label: nd.name })));
  }, [nodes]);

  const [requestText, setRequestText] = useState(() => {
    const transferredPrompt = sessionStorage.getItem("scenario:promptDraft");
    if (!transferredPrompt) return DEFAULT_TEXT;
    sessionStorage.removeItem("scenario:promptDraft");
    return transferredPrompt;
  });
  const [parseState, setParseState] = useState<"idle" | "parsing" | "done">("done");
  const [pills, setPills] = useState<string[]>(["부산 (KRPUS)", "함부르크 (DEHAM)", "세단 10대", "우선순위 COST"]);
  const [form, setForm] = useState<NegotiationForm>(DEFAULT_FORM);
  const [formCollapsed, setFormCollapsed] = useState(false);

  const [step, setStep] = useState<Step>(2);
  const [consoleVisible, setConsoleVisible] = useState(false);
  const [resultsVisible, setResultsVisible] = useState(false);
  const [job, setJob] = useState<NegotiationJob>(EMPTY_JOB);
  const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
  const [etd, setEtd] = useState(defaultEtd);
  const [etdTime, setEtdTime] = useState("08:00");
  const [deadline, setDeadline] = useState(defaultDeadline);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollTimer = useRef<number | null>(null);

  function updateForm(patch: Partial<NegotiationForm>) {
    setForm((f) => ({ ...f, ...patch }));
  }

  function handleParse() {
    setParseState("parsing");
    setTimeout(() => {
      const parsed = parseNegotiationText(requestText, nodes ?? []);
      const patch: Partial<NegotiationForm> = {};
      if (parsed.origin) patch.origin = parsed.origin;
      if (parsed.destination) patch.destination = parsed.destination;
      if (parsed.vehicleType) patch.vehicleType = parsed.vehicleType;
      if (parsed.quantity) patch.quantity = parsed.quantity;
      if (parsed.axis) patch.axis = parsed.axis;
      if (parsed.maxTransitDays) {
        const d = new Date(`${etd}T00:00:00`);
        d.setDate(d.getDate() + parsed.maxTransitDays);
        setDeadline(d.toISOString().slice(0, 10));
      }
      updateForm(patch);
      setPills(parsed.pills.length ? parsed.pills : pills);
      setParseState("done");
      setFormCollapsed(false);
    }, 400);
  }

  function stopPolling() {
    if (pollTimer.current) window.clearInterval(pollTimer.current);
    pollTimer.current = null;
  }

  // overrides가 있으면(자연어 박스에서 바로 실행) 그 값 기준으로 돌리고,
  // 나중에 form에도 반영해서 "요청 편집"이 실제로 실행된 값을 보여주게 한다.
  async function startAnalysis(overrides?: Partial<NegotiationForm>, maxDaysOverride?: number) {
    const effective = { ...form, ...overrides };
    if (overrides) updateForm(overrides);

    let maxTransitDays = daysBetween(etd, deadline);
    if (maxDaysOverride) {
      maxTransitDays = maxDaysOverride;
      const d = new Date(`${etd}T00:00:00`);
      d.setDate(d.getDate() + maxDaysOverride);
      setDeadline(d.toISOString().slice(0, 10));
    }
    if (maxTransitDays <= 0) {
      setError("납기 제약이 출발가능일보다 앞서 있습니다. 날짜를 다시 확인해주세요.");
      return;
    }

    setStep(3);
    setFormCollapsed(true);
    setConsoleVisible(true);
    setResultsVisible(false);
    setSelectedRouteId(null);
    setError(null);
    setLoading(true);
    setJob(EMPTY_JOB);
    stopPolling();

    try {
      const started = await startNegotiation({
        origin: effective.origin,
        destination: effective.destination,
        vehicle_type: effective.vehicleType,
        quantity: effective.quantity,
        selected_axis: effective.axis,
        top_k: effective.topK,
        max_transit_days: maxTransitDays,
      });

      pollTimer.current = window.setInterval(async () => {
        try {
          const latest = await getNegotiation(started.request_id);
          setJob(latest);
          if (latest.status === "PROCESSING") return;

          stopPolling();
          setLoading(false);
          if (latest.status === "FAILED") {
            setError(latest.error ?? "협상 중 오류가 발생했습니다.");
            return;
          }

          const result = latest.result;
          if (!result || result.status !== "completed" || !result.routes.length) {
            setError(result?.error ?? "실행 가능한 경로를 찾지 못했습니다.");
            return;
          }
          const rec = result.recommendation_sets[effective.axis] ?? result.recommendation_sets.COST;
          setSelectedRouteId(rec?.recommended_route_id ?? result.routes[0].route_id);
          setStep(4);
          setResultsVisible(true);
        } catch (e) {
          stopPolling();
          setLoading(false);
          setError(e instanceof Error ? e.message : "진행 상황 조회 중 오류가 발생했습니다.");
        }
      }, 1500);
    } catch (e) {
      setLoading(false);
      setError(e instanceof Error ? e.message : "요청 처리 중 오류가 발생했습니다.");
    }
  }

  // 자연어 텍스트에서 바로 실행 — 출발지·도착지가 둘 다 안 잡히면 실행하지
  // 않고 에러만 띄운다 (엉뚱한 값으로 조용히 도는 것보다 낫다).
  function startAnalysisFromText() {
    const parsed = parseNegotiationText(requestText, nodes ?? []);
    if (!parsed.origin || !parsed.destination) {
      setConsoleVisible(false);
      setError("텍스트에서 출발지·도착지를 둘 다 찾지 못했습니다. 우리 데이터에 있는 지명 그대로 적었는지 확인하거나, 아래 요청 편집에서 직접 골라주세요.");
      return;
    }
    const patch: Partial<NegotiationForm> = { origin: parsed.origin, destination: parsed.destination };
    if (parsed.vehicleType) patch.vehicleType = parsed.vehicleType;
    if (parsed.quantity) patch.quantity = parsed.quantity;
    if (parsed.axis) patch.axis = parsed.axis;
    setPills(parsed.pills.length ? parsed.pills : pills);
    setParseState("done");
    startAnalysis(patch, parsed.maxTransitDays);
  }

  useEffect(() => () => stopPolling(), []);

  function reset() {
    stopPolling();
    setFormCollapsed(false);
    setConsoleVisible(false);
    setResultsVisible(false);
    setStep(2);
    setJob(EMPTY_JOB);
    setError(null);
    setLoading(false);
  }

  const routes = job.result?.routes ?? [];

  // isFavorite=true  → "제안서 보관함에 저장" (북마크 표시를 켠 채로 등록)
  // isFavorite=false → "이 경로 선택" (트래킹용 등록, 북마크 표시는 안 건드림)
  async function handleSave(routeId: string, isFavorite: boolean): Promise<SavedScenario> {
    const r = routes.find((x) => x.route_id === routeId);
    if (!r) throw new Error("경로를 찾을 수 없습니다.");
    const saved = await saveNegotiationRoute(job.request_id, {
      route_id: routeId,
      etd: `${etd}T${etdTime}:00`,
      is_favorite: isFavorite,
    });
    onSave();
    return saved;
  }

  const originNode = nodes?.find((nd) => nd.node_id === form.origin);
  const destNode = nodes?.find((nd) => nd.node_id === form.destination);

  return (
    <section id="scenario" className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div>
          <div className="eyebrow">
            <i className="ti ti-sparkles" />
            LLM Multi-Agent Negotiation
          </div>
          <h3>운송 시나리오 빌더</h3>
          <p>
            실제 LLM이 운송사 에이전트 역할을 맡아 구간별로 협상하고, 근거와 함께 경로를 추천합니다.
            <br />
            <span style={{ color: "var(--muted)", fontSize: 12 }}>
              <i className="ti ti-clock" /> 보통 1~5분 걸리며, 화면을 이동해도 백엔드에서 계속 진행됩니다.
            </span>
          </p>
        </div>
        <div className="hactions">
          <button className="btn" onClick={reset}>
            <i className="ti ti-rotate" />
            초기화
          </button>
        </div>
      </div>

      <div className="steps">
        <div className={`step ${step > 1 ? "done" : "on"}`} data-s="1">
          <span className="n">1</span>
          <span className="t">자연어 요청</span>
        </div>
        <div className={`stepsep ${step > 2 ? "done" : ""}`}>
          <i />
        </div>
        <div className={`step ${step === 2 ? "on" : step > 2 ? "done" : ""}`} data-s="2">
          <span className="n">2</span>
          <span className="t">요청 편집</span>
        </div>
        <div className={`stepsep ${step > 3 ? "done" : ""}`}>
          <i />
        </div>
        <div className={`step ${step === 3 ? "on" : step > 3 ? "done" : ""}`} data-s="3">
          <span className="n">3</span>
          <span className="t">에이전트 협상</span>
        </div>
        <div className={`stepsep ${step > 3 ? "done" : ""}`}>
          <i />
        </div>
        <div className={`step ${step === 4 ? "on" : ""}`} data-s="4">
          <span className="n">4</span>
          <span className="t">제안 비교·승인</span>
        </div>
      </div>

      <section className="card" style={{ marginBottom: 14 }}>
        <div className="card-hd">
          <div>
            <h4>자연어 운송 요청</h4>
            <p>규칙 기반 파서가 출발지·도착지·수량·차종·우선순위 키워드를 구조화합니다</p>
          </div>
          <div className="spacer" />
          <span className={`badge ${parseState === "done" ? "b-blue" : "b-gray"}`}>
            <i className={`ti ${parseState === "parsing" ? "ti-loader-2" : "ti-circle-check"}`} />
            {parseState === "parsing" ? "구조화 중…" : "구조화 완료"}
          </span>
        </div>
        <div className="card-bd">
          <textarea className="reqbox" value={requestText} onChange={(e) => setRequestText(e.target.value)} />
          <div className="okbar">
            <span style={{ fontSize: 11.5, color: "var(--faint)" }}>
              <i className="ti ti-info-circle" /> 이 텍스트 자체는 LLM이 아니라 단순 문자열 매칭입니다. "확인"은 아래 요청 편집 값만 채우고, 실제
              실행은 항상 요청 편집 기준입니다.
            </span>
            <div className="spacer" />
            <button className="btn" onClick={() => setRequestText(DEFAULT_TEXT)}>
              <i className="ti ti-refresh" />
              예시 불러오기
            </button>
            <button className="btn" onClick={handleParse}>
              <i className="ti ti-check" />
              확인 (미리보기만)
            </button>
            <button className="btn blue" onClick={startAnalysisFromText} disabled={loading}>
              <i className="ti ti-player-play-filled" />이 문장으로 바로 실행
            </button>
          </div>
          <div className="parsed">
            {pills.map((p) => (
              <span className="pill" key={p}>
                {p}
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className={`card ${formCollapsed ? "collapsed" : ""}`} id="flowBuilder" style={{ marginBottom: 14, overflow: "hidden" }}>
        <div className="card-hd">
          <div>
            <h4>운송 플로우 빌더</h4>
            <p>실제 운송사 데이터에 있는 노드만 선택할 수 있습니다</p>
          </div>
          <div className="spacer" />
          <span className="pill">
            <i className="ti ti-git-branch" />
            노드 {nodes?.length ?? 0} · 연결 3
          </span>
          <button className="btn sm" onClick={() => setFormCollapsed((c) => !c)}>
            <i className={`ti ${formCollapsed ? "ti-chevrons-down" : "ti-chevrons-up"}`} />
            {formCollapsed ? "펼치기" : "접기"}
          </button>
          <button className="btn blue" onClick={() => startAnalysis()} disabled={loading}>
            <i className="ti ti-player-play-filled" />
            {loading ? "협상 진행 중..." : "AI 분석 시작"}
          </button>
        </div>
        <div className="buildersum">
          <span className="badge b-gray">
            <i className="ti ti-git-branch" />
            플로우 6블록
          </span>
          <span className="pill">
            {originNode?.name ?? form.origin} → {destNode?.name ?? form.destination}
          </span>
          <span className="pill">
            {form.vehicleType} {form.quantity}대
          </span>
          <span className="pill">{AXIS_OPTIONS.find((a) => a.value === form.axis)?.label}</span>
          <div className="spacer" />
          <button className="btn sm" onClick={() => setFormCollapsed(false)}>
            <i className="ti ti-chevrons-down" />
            플로우 다시 열기
          </button>
        </div>
        {!formCollapsed && (
          <div className="builder">
            <div className="library">
              <div className="sectlabel">Location</div>
              <div className="libitem">
                <i className="ti ti-map-pin" />
                출발지
              </div>
              <div className="libitem">
                <i className="ti ti-flag" />
                도착지
              </div>
              <div className="sectlabel" style={{ marginTop: 14 }}>
                Cargo
              </div>
              <div className="libitem green">
                <i className="ti ti-box" />
                화물 정보
              </div>
              <div className="sectlabel" style={{ marginTop: 14 }}>
                Priority
              </div>
              <div className="libitem purple">
                <i className="ti ti-calendar-due" />
                납기 제약
              </div>
              <div className="libitem orange">
                <i className="ti ti-adjustments" />
                우선순위
              </div>
            </div>
            <div className="fcanvas">
              <div className="flow-stage-label"><span>ROUTE</span><b>운송 구간 설정</b><em>출발지와 최종 도착지를 연결합니다</em></div>
              <div className="frow flow-route-row">
                <NodeSearchInput label="출발지" variant="origin" nodes={nodes ?? []} value={form.origin} onChange={(nodeId) => updateForm({ origin: nodeId })} wide />
                <div className="hlink"><span><i className="ti ti-arrow-right" /> 운송 경로</span></div>
                <NodeSearchInput label="도착지" variant="destination" nodes={nodes ?? []} value={form.destination} onChange={(nodeId) => updateForm({ destination: nodeId })} wide />
              </div>
              <div className="vlink"><span>화물 연결</span></div>
              <div className="frow flow-cargo-row">
                <div className="node green wide flow-cargo-node">
                  <div className="flow-node-head">
                    <span className="flow-node-icon"><i className="ti ti-box" /></span>
                    <div><small>STEP 03</small><div className="nt">화물 정보</div></div>
                  </div>
                  <div className="nrow" style={{ borderTop: 0, paddingTop: 0, marginTop: 9 }}>
                    <div>
                      <span>차종</span>
                      <select
                        value={form.vehicleType}
                        onChange={(e) => updateForm({ vehicleType: e.target.value as CargoType })}
                        style={{ border: "none", background: "transparent", fontWeight: 700, fontSize: 12.5 }}
                      >
                        {VEHICLE_OPTIONS.map((v) => (
                          <option key={v} value={v}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <span>수량</span>
                      <input
                        type="number"
                        min={1}
                        value={form.quantity}
                        onChange={(e) => updateForm({ quantity: Number(e.target.value) })}
                        style={{ border: "none", background: "transparent", fontWeight: 700, fontSize: 12.5, width: 60 }}
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="vlink flow-branch-link"><span>운송 조건</span></div>
              <div className="frow three flow-condition-row">
                <div className="flow-stage-label condition"><span>CONDITION</span><b>실행 조건 설정</b><em>일정과 최적화 기준을 적용합니다</em></div>
                <div className="node red flow-condition-node">
                  <div className="nt">
                    <i className="ti ti-calendar-due" />
                    출발가능일
                  </div>
                  <input type="date" className="nv" value={etd} onChange={(e) => setEtd(e.target.value)} style={{ border: "none", width: "100%", background: "transparent" }} />
                  <div className="ns">이 날짜부터 출발 가능하다고 보고 협상합니다</div>
                </div>
                <div className="node purple flow-condition-node">
                  <div className="nt">
                    <i className="ti ti-calendar-due" />
                    납기 제약
                  </div>
                  <input type="date" className="nv" min={etd} value={deadline} onChange={(e) => setDeadline(e.target.value)} style={{ border: "none", width: "100%", background: "transparent" }} />
                  <div className="ns">
                    {daysBetween(etd, deadline) > 0
                      ? `최대 ${daysBetween(etd, deadline)}일 · 하드 제약`
                      : "출발가능일보다 늦어야 합니다"}
                  </div>
                </div>
                <div className="node orange flow-condition-node">
                  <div className="nt">
                    <i className="ti ti-adjustments" />
                    우선순위
                  </div>
                  <select
                    className="nv"
                    value={form.axis}
                    onChange={(e) => updateForm({ axis: e.target.value as Axis })}
                    style={{ border: "none", width: "100%", background: "transparent" }}
                  >
                    {AXIS_OPTIONS.map((a) => (
                      <option key={a.value} value={a.value}>
                        {a.label}
                      </option>
                    ))}
                  </select>
                  <div className="ns">협상 시 최적화 기준</div>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>

      {error && (
        <div className="card" style={{ marginBottom: 14, padding: 16, color: "var(--danger)" }}>
          <i className="ti ti-alert-triangle" /> {error}
        </div>
      )}

      {consoleVisible && (
        <section>
          <NegotiationConsole status={job.status} progress={job.progress} stage={job.stage} message={job.message} events={job.events} startedAt={job.started_at} />
        </section>
      )}

      {resultsVisible && job.result && (
        <NegotiationResults
          result={job.result}
          selectedId={selectedRouteId}
          onSelect={setSelectedRouteId}
          etd={`${etd}T${etdTime}`}
          onEtdChange={(v) => {
            const [d, t] = v.split("T");
            if (d) setEtd(d);
            if (t) setEtdTime(t);
          }}
          onSave={handleSave}
          onOpenTrace={(route) => onOpenDrawer(buildTraceDrawer(route, job))}
          onNavigateToTracking={onNavigateToTracking}
        />
      )}
    </section>
  );
}
