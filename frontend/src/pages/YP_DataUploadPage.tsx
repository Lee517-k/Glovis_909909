import { useRef, useState } from "react";
import { Badge } from "../lib/YP_ui";
// 업로드 페이지 안에 "운송사 역량 가시화" 탭을 추가하면서, 별도 페이지였던 지도/그리드 패널을 가져와 재사용
import { YpCarrierNetworkPanel } from "./YP_CarrierVisualizationPanel";
import "./YP_glovis_primitives.css";
import "./YP_data.css";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

type UploadAnalysis = {
  upload_id: string;
  file_name: string;
  carrier_name: string;
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  warning_count: number;
  headers: string[];
  mapping: {
    system_field: string;
    source_column: string | null;
    required: boolean;
    status: "mapped" | "excluded";
  }[];
  issues: { row: number; errors: string[]; data_errors?: string[]; warnings: string[]; data_warnings?: string[] }[];
  preview: Record<string, unknown>[];
};

// 데이터 페이지: "데이터 업로드"(3단계 업로드 플로우)와 "운송사 역량 가시화"(지도/그리드) 두 탭을 가진다.
// 업로드 플로우는 파일 분석(analyze) -> 컬럼 매핑 확인/수정(remap) -> DB 반영(commit) 3단계로 진행된다.
export function UploadPage({ active }: { active: boolean }) {
  // 역량 가시화 패널을 같은 페이지 안에서 탭으로 전환하기 위한 상태 (기존에는 업로드 화면만 있었음)
  const [tab, setTab] = useState<"upload" | "net">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [carrierName, setCarrierName] = useState("");
  const [analysis, setAnalysis] = useState<UploadAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [remapping, setRemapping] = useState(false);
  const [committed, setCommitted] = useState<number | null>(null);
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);

  // 업로드용 엑셀 템플릿 파일을 백엔드에서 받아 즉시 다운로드
  const downloadTemplate = () => {
    const anchor = document.createElement("a");
    anchor.href = `${API_BASE}/yp/uploads/template`;
    anchor.download = "glovis_carrier_capability_template.xlsx";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  };

  // 1단계: 선택된 파일을 백엔드로 보내 분석(자동 매핑 + 행 검증)을 요청한다. DB에는 아직 반영되지 않는다.
  const analyzeFile = async (selected: File) => {
    // 선사명은 DB의 carrier_name으로 저장되므로 서버 호출 전에 먼저 검증
    if (!carrierName.trim()) {
      setError("선사 이름을 입력해 주세요.");
      return;
    }
    setFile(selected);
    setAnalysis(null);
    setCommitted(null);
    setError("");
    setLoading(true);
    try {
      const body = new FormData();
      body.append("file", selected);
      body.append("carrier_name", carrierName.trim());
      const response = await fetch(`${API_BASE}/yp/uploads/analyze`, {
        method: "POST",
        body,
      });
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? `분석 실패 (${response.status})`);
      setAnalysis(payload);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "파일 분석에 실패했습니다.",
      );
    } finally {
      setLoading(false);
    }
  };

  // 3단계: 검증을 통과한 행들을 실제 carrier_capabilities DB에 반영
  const commitUpload = async () => {
    if (!analysis) return;
    setCommitting(true);
    setError("");
    try {
      const response = await fetch(
        `${API_BASE}/yp/uploads/${analysis.upload_id}/commit`,
        { method: "POST" },
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? `DB 반영 실패 (${response.status})`);
      setCommitted(payload.inserted_or_updated);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "DB 반영에 실패했습니다.",
      );
    } finally {
      setCommitting(false);
    }
  };

  // 2단계(선택): 사용자가 매핑 테이블에서 특정 시스템 필드의 원본 컬럼을 바꾸면, 전체 매핑을 서버로 다시 보내 재검증한다.
  const remapField = async (systemField: string, sourceColumn: string) => {
    if (!analysis) return;
    setRemapping(true);
    setError("");
    const mappings = Object.fromEntries(
      analysis.mapping.map((item) => [item.system_field, item.source_column]),
    );
    mappings[systemField] = sourceColumn || null;
    try {
      const response = await fetch(
        `${API_BASE}/yp/uploads/${analysis.upload_id}/remap`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mappings }),
        },
      );
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.detail ?? `재매핑 실패 (${response.status})`);
      setAnalysis(payload);
      setCommitted(null);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "컬럼 재매핑에 실패했습니다.",
      );
    } finally {
      setRemapping(false);
    }
  };

  // 현재 분석 결과를 지우고 새 파일을 올릴 수 있도록 초기 상태로 되돌린다
  const reset = () => {
    setFile(null);
    setCarrierName("");
    setAnalysis(null);
    setCommitted(null);
    setError("");
    if (input.current) input.current.value = "";
  };
  const step = committed !== null ? 2 : analysis ? 1 : 0;
  // 이슈 목록에서 행 검증 오류만 모아 중복 제거 후 상위 3개만 카드에 요약 표시
  const errorMessages = [
    ...new Set(
      analysis?.issues.flatMap((issue) =>
        (issue.data_errors ?? []).map(
          (message) => `${issue.row}행: ${message}`,
        ),
      ) ?? [],
    ),
  ].slice(0, 3);
  // 위와 동일한 방식으로 경고 메시지만 모아 상위 3개 요약
  const warningMessages = [
    ...new Set(
      analysis?.issues.flatMap((issue) =>
        (issue.data_warnings ?? []).map(
          (message) => `${issue.row}행: ${message}`,
        ),
      ) ?? [],
    ),
  ].slice(0, 3);

  return (
    <section id="upload" className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div>
          <div className="eyebrow">
            <i className="ti ti-database" />
            Carrier Data
          </div>
          <h3>데이터</h3>
          <p>
            운송사 원본 데이터를 올려 시스템 필드에 매핑하고, 승인된 역량
            데이터를 네트워크로 확인합니다.
          </p>
        </div>
        <div className="hactions">
          <button className="btn" onClick={downloadTemplate}>
            <i className="ti ti-download" />
            템플릿 받기
          </button>
        </div>
      </div>
      {/* 업로드 화면과 역량 가시화 화면을 페이지 이동 없이 탭으로 전환하기 위해 추가 */}
      <nav className="yp-data-tabs" aria-label="데이터 화면 탭">
        <button
          className={`yp-data-tab ${tab === "upload" ? "active" : ""}`}
          onClick={() => setTab("upload")}
        >
          <i className="ti ti-upload" />
          데이터 업로드
        </button>
        <button
          className={`yp-data-tab ${tab === "net" ? "active" : ""}`}
          onClick={() => setTab("net")}
        >
          <i className="ti ti-chart-dots-3" />
          운송사 역량 가시화
        </button>
      </nav>
      {tab === "net" ? (
        <YpCarrierNetworkPanel refreshKey={active} />
      ) : (
        <>
          <div className="yp-upload-flow">
            {[
              ["원본 파일 업로드", "xlsx · csv · pdf"],
              ["검증 및 확인", "오류·경고 항목 확인"],
              ["DB 반영", "승인된 역량 저장"],
            ].map((item, index) => (
              <div
                className={`yp-flow-step ${index < step ? "done" : index === step ? "active" : ""}`}
                key={item[0]}
              >
                <span className="n">{index + 1}</span>
                <div>
                  <b>{item[0]}</b>
                  <span>{item[1]}</span>
                </div>
              </div>
            ))}
          </div>
          {error && (
            <div className="yp-aialert yp-error" style={{ marginBottom: 14 }}>
              <b>처리할 수 없습니다.</b>
              <br />
              {error}
            </div>
          )}
          {!analysis ? (
            <div className="yp-upload-hero">
              <section className="card">
                <div className="card-hd">
                  <div>
                    <h4>운송사 역량 원본 업로드</h4>
                    <p>제공된 템플릿 또는 표가 포함된 PDF를 업로드하세요.</p>
                  </div>
                  <div className="spacer" />
                  <Badge tone="blue">선사명 필수</Badge>
                </div>
                <div className="card-bd">
                  {/* carrier_name이 DB의 필수 식별자라 파일 선택 전에 먼저 입력받도록 추가 */}
                  <div className="yp-carrier-name-field">
                    <label htmlFor="yp-carrier-name">
                      선사 이름 <em>필수</em>
                    </label>
                    <div className="yp-carrier-name-input">
                      <i className="ti ti-building-warehouse" />
                      <input
                        id="yp-carrier-name"
                        value={carrierName}
                        onChange={(event) => setCarrierName(event.target.value)}
                        placeholder="예: 현대글로비스"
                        disabled={loading}
                      />
                    </div>
                    <p>입력한 이름은 SQLite의 carrier_name으로 저장됩니다.</p>
                  </div>
                  <div
                    className="dropzone"
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      const selected = event.dataTransfer.files[0];
                      if (selected) void analyzeFile(selected);
                    }}
                  >
                    <i
                      className={`ti ${loading ? "ti-loader-2" : "ti-cloud-upload"}`}
                      style={{ fontSize: 34, color: "var(--blue)" }}
                    />
                    <div
                      style={{ fontSize: 15, fontWeight: 750, marginTop: 9 }}
                    >
                      {loading
                        ? "파일을 분석하고 있습니다..."
                        : "분석할 파일을 여기에 놓으세요"}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: "var(--faint)",
                        marginTop: 4,
                      }}
                    >
                      xlsx · csv · pdf · 최대 20MB
                    </div>
                    <button
                      className="btn blue"
                      style={{ marginTop: 15 }}
                      disabled={loading}
                      onClick={() => input.current?.click()}
                    >
                      <i className="ti ti-folder-open" />
                      파일 선택
                    </button>
                    <input
                      ref={input}
                      type="file"
                      accept=".xlsx,.xlsm,.csv,.pdf"
                      hidden
                      onChange={(event) => {
                        const selected = event.target.files?.[0];
                        if (selected) void analyzeFile(selected);
                      }}
                    />
                  </div>
                  <div
                    style={{
                      textAlign: "center",
                      marginTop: 12,
                      color: "var(--faint)",
                      fontSize: 11.5,
                    }}
                  >
                    분석 단계에서는 DB가 변경되지 않습니다.
                  </div>
                </div>
              </section>
              <aside className="yp-upload-side">
                <h5>업로드 처리 원칙</h5>
                <ul>
                  <li>
                    <i className="ti ti-table" />
                    <span>
                      <b>Excel 컬럼 매핑</b>
                      <br />
                      템플릿 및 일반적인 운임표 헤더를 시스템 필드로 변환합니다.
                    </span>
                  </li>
                  <li>
                    <i className="ti ti-file-type-pdf" />
                    <span>
                      <b>PDF 표 추출</b>
                      <br />표 구조가 확인되는 PDF만 분석하며 불확실한 문서는
                      저장하지 않습니다.
                    </span>
                  </li>
                  <li>
                    <i className="ti ti-shield-check" />
                    <span>
                      <b>행 단위 검증</b>
                      <br />
                      필수값, 운송수단, 숫자와 비율 범위를 검사합니다.
                    </span>
                  </li>
                  <li>
                    <i className="ti ti-database-plus" />
                    <span>
                      <b>승인 후 트랜잭션</b>
                      <br />
                      유효 행과 원본 evidence를 한 번에 저장합니다.
                    </span>
                  </li>
                </ul>
              </aside>
            </div>
          ) : (
            <>
              <div className="yp-analysis-head">
                <div>
                  <span className="yp-analysis-kicker">UPLOAD REVIEW</span>
                  <h4>업로드 파일 검증 결과</h4>
                  <p>
                    현재 파일을 검토하거나 새 파일로 다시 시작할 수 있습니다.
                  </p>
                </div>
                <button className="btn yp-new-upload-btn" onClick={reset}>
                  <i className="ti ti-file-plus" />
                  <span>
                    <b>새 파일 업로드</b>
                    <small>현재 결과를 닫고 다시 선택</small>
                  </span>
                </button>
              </div>
              <div style={{ marginBottom: 14 }}>
                <section className="card yp-upload-result-card">
                  <div className="card-hd">
                    <div>
                      <h4>업로드 파일</h4>
                      <p>실제 백엔드 분석 결과입니다.</p>
                    </div>
                    <div className="spacer" />
                    <Badge tone="blue">
                      {analysis.carrier_name || carrierName}
                    </Badge>
                  </div>
                  <div className="card-bd">
                    <div className="yp-filechip">
                      <i
                        className="ti ti-file-spreadsheet"
                        style={{ fontSize: 21, color: "var(--ok)" }}
                      />
                      <div style={{ flex: 1 }}>
                        <b>{file?.name ?? analysis.file_name}</b>
                        <div style={{ fontSize: 11, color: "var(--muted)" }}>
                          {analysis.total_rows.toLocaleString()}행 ·{" "}
                          {analysis.headers.length}개 원본 컬럼
                        </div>
                      </div>
                    </div>
                    <div className="yp-metricchips">
                      <div className="yp-metricchip">
                        <span>유효 행</span>
                        <b>{analysis.valid_rows.toLocaleString()}</b>
                      </div>
                      <div className="yp-metricchip">
                        <span>오류 행</span>
                        <b style={{ color: "var(--danger)" }}>
                          {analysis.invalid_rows.toLocaleString()}
                        </b>
                      </div>
                      <div className="yp-metricchip">
                        <span>경고</span>
                        <b style={{ color: "var(--warn)" }}>
                          {analysis.warning_count.toLocaleString()}
                        </b>
                      </div>
                    </div>
                    {(errorMessages.length > 0 || warningMessages.length > 0) && (
                      <div
                        className={`yp-issue-stack ${
                          errorMessages.length > 0 && warningMessages.length > 0
                            ? "dual"
                            : ""
                        }`}
                      >
                        {errorMessages.length > 0 && (
                          <div className="yp-issue-box yp-issue-danger">
                            <i className="ti ti-circle-x" />
                            <div>
                              <b>사용할 수 없는 행이 있습니다.</b>
                              {errorMessages.map((message) => (
                                <p key={message}>{message}</p>
                              ))}
                            </div>
                          </div>
                        )}
                        {warningMessages.length > 0 && (
                          <div className="yp-issue-box yp-issue-warning">
                            <i className="ti ti-alert-triangle" />
                            <div>
                              <b>확인이 필요한 행이 있습니다.</b>
                              {warningMessages.map((message) => (
                                <p key={message}>{message}</p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </section>
              </div>
              <details
                className="card yp-mapping-details"
                style={{ marginBottom: 14 }}
                open
              >
                <summary>
                  <div>
                    <h4>컬럼 매핑 확인</h4>
                    <p>
                      SQLite 시스템 필드는 고정입니다. 원본 파일의 열만 선택할
                      수 있습니다.
                    </p>
                  </div>
                  <div className="spacer" />
                  <Badge tone="blue">
                    {
                      analysis.mapping.filter(
                        (item) => item.status === "mapped",
                      ).length
                    }{" "}
                    / {analysis.mapping.length} 매핑
                  </Badge>
                  <i className="ti ti-chevron-down yp-details-chevron" />
                </summary>
                <div className="tablewrap yp-mapping-table">
                  <table>
                    <thead>
                      <tr>
                        <th>원본 컬럼 선택</th>
                        <th></th>
                        <th>SQLite 시스템 필드</th>
                        <th>필수</th>
                        <th>상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {analysis.mapping.map((item) => (
                        <tr key={item.system_field}>
                          <td>
                            <select
                              className="yp-mapping-select"
                              value={item.source_column ?? ""}
                              disabled={remapping}
                              onChange={(event) =>
                                void remapField(
                                  item.system_field,
                                  event.target.value,
                                )
                              }
                            >
                              <option value="">매핑하지 않음</option>
                              {analysis.headers.map((header) => (
                                <option key={header} value={header}>
                                  {header}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="yp-map-arrow">→</td>
                          <td className="mono yp-system-field">
                            {item.system_field}
                          </td>
                          <td>
                            {item.required ? (
                              <Badge tone="warn">필수</Badge>
                            ) : (
                              <span className="yp-optional">선택</span>
                            )}
                          </td>
                          <td>
                            <Badge
                              tone={item.status === "mapped" ? "ok" : "danger"}
                            >
                              {item.status === "mapped" ? "매핑" : "제외"}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {remapping && (
                  <div className="yp-remapping">
                    <i className="ti ti-loader-2" /> 매핑을 다시 검증하고
                    있습니다.
                  </div>
                )}
              </details>
              <section className="card">
                <div
                  className="card-bd"
                  style={{ display: "flex", alignItems: "center", gap: 12 }}
                >
                  <i
                    className="ti ti-database-check"
                    style={{ fontSize: 25, color: "var(--blue)" }}
                  />
                  <div>
                    <b>
                      {committed !== null
                        ? "DB 반영이 완료되었습니다"
                        : "유효 데이터 DB 반영"}
                    </b>
                    <div style={{ fontSize: 11.5, color: "var(--muted)" }}>
                      {committed !== null
                        ? `${committed}개 역량이 저장되었습니다. 다음 파일을 이어서 업로드할 수 있습니다.`
                        : `유효 ${analysis.valid_rows}행을 저장하고 오류 ${analysis.invalid_rows}행은 제외합니다.`}
                    </div>
                  </div>
                  <div className="spacer" />
                  {committed !== null ? (
                    <button
                      className="btn blue yp-next-upload-btn"
                      onClick={reset}
                    >
                      <i className="ti ti-upload" />
                      다음 파일 업로드
                    </button>
                  ) : (
                    <button
                      className="btn blue"
                      disabled={committing || analysis.valid_rows === 0}
                      onClick={() => void commitUpload()}
                    >
                      {committing
                        ? "반영 중..."
                        : `${analysis.valid_rows}행 승인 및 반영`}
                    </button>
                  )}
                </div>
              </section>
            </>
          )}
        </>
      )}
    </section>
  );
}

