import { Fragment, useEffect, useState } from "react";
import { Badge } from "../lib/YP_ui";
import "./YP_glovis_primitives.css";
import "./YP_data.css";

type Carrier = {
  carrier_id: string;
  carrier_name: string;
  score: number;
  status: "verified" | "review" | "unverified";
  validated_count: number;
  candidates: number;
};

type Metric = {
  capability_id: string;
  metric: string;
  db_value: string;
  actual_value: string;
  error: string;
  verdict: "허용 범위" | "보정 필요" | "검증 필요" | "검증 대기";
  reason: string;
  action: string;
};

type Detail = Carrier & {
  hit_rate: number;
  cost_error: number;
  days_error: number;
  coverage: number;
  historical_count: number;
  verified_capability_count: number;
  total_capability_count: number;
  metrics: Metric[];
  verified_metrics: Metric[];
  impact: string;
};

type Similarity = {
  capability_id: string;
  similar: boolean;
  confidence: number;
  reason: string;
  reference_leg_ids: string[];
};

const blank: Detail = {
  carrier_id: "",
  carrier_name: "",
  score: 0,
  status: "unverified",
  validated_count: 0,
  candidates: 0,
  hit_rate: 0,
  cost_error: 0,
  days_error: 0,
  coverage: 0,
  historical_count: 0,
  verified_capability_count: 0,
  total_capability_count: 0,
  metrics: [],
  verified_metrics: [],
  impact: "검증 이력이 없습니다.",
};

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");
const ACTION_STATUS: Record<string, string> = {
  "보정 후보 유지": "correction_candidate",
  "검증 완료": "verified",
  "운송사 응답 대기 중": "awaiting_carrier_response",
  "계산 제외": "excluded",
};

function statusLabel(carrier: Carrier) {
  if (carrier.status === "verified") return "신뢰 가능";
  if (carrier.validated_count === 0) return "검증 대기";
  return "보정 필요";
}

function DbValue({ value }: { value: string }) {
  return <span className="yp-db-value">{value.split(" · ").map((line) => <span key={line}>{line}</span>)}</span>;
}

export function YpDataReliabilityPage({ active }: { active: boolean }) {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<Detail>(blank);
  const [actions, setActions] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [backtesting, setBacktesting] = useState(false);
  const [view, setView] = useState<"candidates" | "verified">("candidates");
  const [expanded, setExpanded] = useState("");
  const [llmLoading, setLlmLoading] = useState(false);
  const [similarities, setSimilarities] = useState<Record<string, Similarity>>({});
  const [llmModel, setLlmModel] = useState("");
  const [similarityMode, setSimilarityMode] = useState<"ollama" | "rule_based" | "">("");
  const [similarityNotice, setSimilarityNotice] = useState("");

  async function loadCarriers() {
    const response = await fetch(`${API_BASE}/yp/reliability`);
    if (!response.ok) throw new Error(`신뢰도 조회 실패 (${response.status})`);
    const data = await response.json();
    const items = data.items ?? [];
    setCarriers(items);
    return items as Carrier[];
  }

  async function loadDetail(carrierId: string) {
    const response = await fetch(`${API_BASE}/yp/reliability/${encodeURIComponent(carrierId)}`);
    if (!response.ok) throw new Error(`상세 조회 실패 (${response.status})`);
    const data: Detail = await response.json();
    setDetail(data);
    setActions(Object.fromEntries(data.metrics.map((metric) => [metric.capability_id, metric.action])));
    setChecked(new Set());
    setView("candidates");
    setExpanded("");
    void previewSimilarCases(carrierId, data.metrics.map((metric) => metric.capability_id));
  }

  async function previewSimilarCases(carrierId = selected, capabilityIds = detail.metrics.map((metric) => metric.capability_id)) {
    if (!carrierId || capabilityIds.length === 0) {
      setSimilarities({});
      return;
    }
    setLlmLoading(true);
    try {
      const response = await fetch(`${API_BASE}/yp/reliability/similarity`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ carrier_id: carrierId, capability_ids: capabilityIds }),
      });
      if (!response.ok) throw new Error(`Ollama 분석 실패 (${response.status})`);
      const data = await response.json();
      setSimilarities(Object.fromEntries((data.items ?? []).map((item: Similarity) => [item.capability_id, item])));
      setLlmModel(data.model ?? "");
      setSimilarityMode(data.mode ?? "ollama");
      setSimilarityNotice(data.notice ?? "");
      setError("");
    } catch (reason) {
      setSimilarities({});
      setError(reason instanceof Error ? reason.message : "Ollama 분석 실패");
    } finally {
      setLlmLoading(false);
    }
  }

  function changeView(next: "candidates" | "verified") {
    setView(next);
    setChecked(new Set());
    setExpanded("");
    if (next === "candidates") void previewSimilarCases();
  }

  async function persistActions(entries: [string, string][], successMessage: string) {
    if (!selected || entries.length === 0) {
      setMessage("처리할 검증 구간을 선택해주세요.");
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/yp/reliability/actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          carrier_id: selected,
          actions: entries.map(([capability_id, action]) => ({ capability_id, status: ACTION_STATUS[action] })),
        }),
      });
      if (!response.ok) throw new Error(`검증 결과 저장 실패 (${response.status})`);
      await loadCarriers();
      await loadDetail(selected);
      setMessage(successMessage);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "검증 결과 저장 실패");
    } finally {
      setLoading(false);
    }
  }

  function toggleAll() {
    setChecked((current) => current.size === detail.metrics.length ? new Set() : new Set(detail.metrics.map((metric) => metric.capability_id)));
  }

  function toggleOne(capabilityId: string) {
    setChecked((current) => {
      const next = new Set(current);
      if (next.has(capabilityId)) next.delete(capabilityId);
      else next.add(capabilityId);
      return next;
    });
  }

  function requestCarrierConfirmation() {
    const entries: [string, string][] = [...checked].map((id) => [id, "운송사 응답 대기 중"]);
    void persistActions(entries, `${entries.length}개 구간을 운송사 응답 대기 상태로 변경했습니다.`);
  }

  function saveResults() {
    void persistActions(Object.entries(actions), "현재 검증 결과와 조치 상태를 저장했습니다.");
  }

  function approveSelected() {
    const entries: [string, string][] = [...checked].map((id) => [id, "검증 완료"]);
    void persistActions(entries, `${entries.length}개 구간을 검증 완료로 반영했습니다.`);
  }

  async function runBacktest() {
    setLoading(true);
    setBacktesting(true);
    setMessage("");
    try {
      const items = await loadCarriers();
      const carrierId = items.some((carrier) => carrier.carrier_id === selected) ? selected : items[0]?.carrier_id;
      if (carrierId) {
        setSelected(carrierId);
        await loadDetail(carrierId);
      }
      setMessage("최신 역량 데이터와 과거 운송 실적으로 신뢰도 계산을 완료했습니다.");
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "DB 연결 실패");
    } finally {
      setLoading(false);
      setBacktesting(false);
    }
  }

  async function selectCarrier(carrierId: string) {
    if (loading || backtesting || carrierId === selected) return;
    setSelected(carrierId);
    setLoading(true);
    setMessage("");
    try {
      await loadDetail(carrierId);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "DB 연결 실패");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void runBacktest();
  }, []);

  return (
    <section id="yp-data-reliability" aria-busy={backtesting} className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div>
          <div className="eyebrow"><i className="ti ti-shield-check" />Data Reliability</div>
          <h3>운송 데이터 신뢰도 검증</h3>
          <p>운송사가 등록한 역량·운임을 과거 실제 운송 결과와 비교해 데이터 신뢰도를 검증합니다.</p>
        </div>
        <div className="hactions">
          <button className={`btn yp-backtest-button ${backtesting ? "is-running" : ""}`} disabled={loading} onClick={() => void runBacktest()}>
            <i className={`ti ${backtesting ? "ti-loader-2 yp-spin" : "ti-refresh"}`} />
            {backtesting ? "신뢰도 재계산 중" : "백테스트 다시 실행"}
          </button>
        </div>
      </div>

      {error && <div className="yp-aialert" style={{ marginBottom: 14 }}><b>데이터를 불러오지 못했습니다.</b><br />{error}</div>}

      <div className={`yp-reliability-workspace ${backtesting ? "is-locked" : ""}`}>
        {backtesting && <div className="yp-backtest-overlay"><div className="yp-backtest-progress"><i className="ti ti-loader-2 yp-spin" /><b>검증 데이터를 다시 계산하고 있습니다</b><span>운송사 역량과 실제 완료 시나리오를 비교하는 중입니다.</span></div></div>}
      <div className="grid yp-relgrid">
        <div className="yp-carrier-list-panel">
          <div className="sectlabel">운송사별 신뢰도 · 실제 완료 시나리오 기준</div>
          {carriers.map((carrier) => (
            <button
              key={carrier.carrier_id}
              className={`yp-carrier-item ${selected === carrier.carrier_id ? "active" : ""}`}
              disabled={loading || backtesting}
              onClick={() => void selectCarrier(carrier.carrier_id)}
            >
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <b>{carrier.carrier_name}</b>
                <Badge tone={carrier.status === "verified" ? "ok" : carrier.score < 60 ? "danger" : "warn"}>
                  {statusLabel(carrier)}
                </Badge>
              </div>
              <div className="yp-scorebar">
                <i style={{ width: `${carrier.score}%`, background: carrier.score >= 90 ? "var(--ok)" : carrier.score < 60 ? "var(--danger)" : "var(--warn)" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--faint)" }}>
                <span>{carrier.validated_count}개 역량 구간 검증</span><b>{carrier.score.toFixed(0)}점</b>
              </div>
            </button>
          ))}
        </div>

        <section className="card yp-reliability-card">
          <div className="card-hd">
            <div><h4>{detail.carrier_name || "운송사"} 운송 데이터 백테스트</h4><p>등록 역량 DB ↔ 과거 실제 운송 완료 구간</p></div>
            <div className="spacer" />
            <div style={{ textAlign: "right" }}><div className="yp-score">{detail.score.toFixed(0)}</div><small style={{ color: "var(--faint)" }}>신뢰도 점수</small></div>
          </div>
          <div className="card-bd">
            <div className="yp-metric-groups">
              <div className="yp-metric-switches">
                <button className={`yp-btmetric ${view === "verified" ? "active" : ""}`} onClick={() => changeView("verified")}><span>검증 완료 구간</span><b>{detail.validated_count}</b><small>실제 완료 이력 확인</small></button>
                <button className={`yp-btmetric ${view === "candidates" ? "active" : ""}`} onClick={() => changeView("candidates")}><span>보정 후보</span><b>{detail.candidates}</b><small>추가 근거 또는 확인 필요</small></button>
              </div>
              <div className="yp-metric-stats">
                {[
                  ["가능 판정 적중", `${detail.hit_rate}%`],
                  ["평균 운임 오차", `${detail.cost_error >= 0 ? "+" : ""}${detail.cost_error}%`],
                  ["평균 일정 오차", `${detail.days_error >= 0 ? "+" : ""}${detail.days_error}일`],
                ].map(([label, value]) => <div className="yp-btmetric" key={label}><span>{label}</span><b>{value}</b></div>)}
              </div>
            </div>

            {message && <div className="yp-save-message">{message}</div>}
            {similarityNotice && <div className="yp-similarity-notice"><i className="ti ti-info-circle" />{similarityNotice}</div>}
            <div className="yp-table-mode">
              <b>{view === "candidates" ? "보정 후보" : "검증 완료 구간"}</b>
              {view === "candidates" && <>
                <span className={llmLoading ? "is-loading" : ""}><i className={`ti ${llmLoading ? "ti-loader-2 yp-spin" : similarityMode === "rule_based" ? "ti-database" : "ti-sparkles"}`} />{llmLoading ? "Ollama 유사 사례 분석 중" : similarityMode === "rule_based" ? "DB 단순 비교 완료" : llmModel ? `${llmModel} 분석 완료` : "Ollama 연결 대기"}</span>
              </>}
            </div>
            <div className="tablewrap yp-reliability-tablewrap">
              {view === "verified" ? (
                <table className="yp-verified-table">
                  <thead><tr><th>검증 구간</th><th>운송사 DB 값</th><th>오차</th><th>판정 근거</th></tr></thead>
                  <tbody>{detail.verified_metrics.map((metric) => <tr key={metric.capability_id}><td><b>{metric.metric}</b></td><td><DbValue value={metric.db_value} /></td><td className="yp-error">{metric.error}</td><td>{metric.reason}</td></tr>)}</tbody>
                </table>
              ) : (
                <table className="yp-candidate-table">
                  <thead><tr><th className="yp-checkcell"><input type="checkbox" aria-label="전체 선택" checked={detail.metrics.length > 0 && checked.size === detail.metrics.length} onChange={toggleAll} /></th><th>검증 구간</th><th>운송사 DB 값</th><th>과거 실제 결과</th><th>판정 근거</th><th>조치</th></tr></thead>
                  <tbody>
                    {detail.metrics.map((metric) => {
                    const analysis = similarities[metric.capability_id];
                    const similar = analysis?.similar ?? false;
                    return <Fragment key={metric.capability_id}>
                      <tr className={similar ? "yp-expandable-row" : ""} onClick={() => similar && setExpanded((current) => current === metric.capability_id ? "" : metric.capability_id)}>
                        <td className="yp-checkcell"><input type="checkbox" aria-label={`${metric.metric} 선택`} checked={checked.has(metric.capability_id)} onClick={(event) => event.stopPropagation()} onChange={() => toggleOne(metric.capability_id)} /></td>
                        <td><b>{metric.metric}</b>{similar && <i className={`ti ti-chevron-${expanded === metric.capability_id ? "up" : "down"}`} />}</td>
                        <td><DbValue value={metric.db_value} /></td>
                        <td>{llmLoading ? "분석 중" : similar ? <Badge tone="blue">유사 사례 {analysis?.confidence ?? 0}%</Badge> : analysis ? "유사 사례 없음" : "분석 대기"}</td>
                        <td>{metric.reason}</td>
                        <td onClick={(event) => event.stopPropagation()}><select className="yp-actsel" value={actions[metric.capability_id] ?? metric.action} onChange={(event) => setActions((current) => ({ ...current, [metric.capability_id]: event.target.value }))}><option>보정 후보 유지</option><option>검증 완료</option><option>운송사 응답 대기 중</option><option>계산 제외</option></select></td>
                      </tr>
                      {similar && analysis && expanded === metric.capability_id && <tr className="yp-similar-detail"><td colSpan={6}><i className="ti ti-sparkles" /><div><b>Ollama 유사 사례 판단 근거</b><p>{analysis.reason}</p>{analysis.reference_leg_ids.length > 0 && <small>참조 이력: {analysis.reference_leg_ids.join(", ")}</small>}</div></td></tr>}
                    </Fragment>;
                  })}</tbody>
                </table>
              )}
            </div>
            {view === "candidates" && <div className="yp-actionrow"><span className="yp-selected-count">{checked.size}개 선택</span><button className="btn sm" disabled={loading || checked.size === 0} onClick={requestCarrierConfirmation}><i className="ti ti-message-circle" />운송사 확인 요청</button><div className="spacer" /><button className="btn sm" disabled={loading} onClick={saveResults}><i className="ti ti-device-floppy" />검증 결과 저장</button><button className="btn primary sm" disabled={loading || checked.size === 0} onClick={approveSelected}><i className="ti ti-check" />보정값 승인 및 DB 반영</button></div>}
          </div>
        </section>
      </div>
      </div>
    </section>
  );
}
