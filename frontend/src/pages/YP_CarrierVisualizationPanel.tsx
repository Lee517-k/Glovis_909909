import { useEffect, useMemo, useState } from "react";

import { getYPCapabilities, getYPSummary, type YPCapability, type YPSummary } from "../api/YP_dataApi";

const MODE_LABEL: Record<string, string> = { sea: "해상", air: "항공", rail: "철도", road: "도로" };

export function YP_CarrierVisualizationPanel() {
  const [summary, setSummary] = useState<YPSummary | null>(null);
  const [capabilities, setCapabilities] = useState<YPCapability[]>([]);
  const [selectedCarrier, setSelectedCarrier] = useState<string>("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([getYPSummary(), getYPCapabilities()])
      .then(([summaryData, capabilityData]) => {
        setSummary(summaryData);
        setCapabilities(capabilityData.items);
        setSelectedCarrier(capabilityData.items[0]?.carrier_id ?? "");
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "조회에 실패했습니다."));
  }, []);

  const carriers = useMemo(() => Array.from(new Map(capabilities.map((item) => [item.carrier_id, item.carrier_name]))), [capabilities]);
  const visibleCapabilities = capabilities.filter((item) => item.carrier_id === selectedCarrier).slice(0, 8);

  return (
    <div className="yp-network-shell">
      {error && <div className="yp-api-error">{error} 백엔드 실행 상태를 확인해주세요.</div>}
      <section className="yp-network-toolbar"><div className="yp-searchbox"><i className="ti ti-search" /><span>운송사 또는 서비스 검색</span></div><button type="button" disabled><i className="ti ti-adjustments-horizontal" /> 필터</button></section>
      <section className="yp-network-kpis">
        {[
          ["등록 운송사", summary?.carriers ?? "-", "ti-building-warehouse"],
          ["운송 서비스", summary?.services ?? "-", "ti-route"],
          ["연결 국가", summary?.countries ?? "-", "ti-world"],
          ["운송 모드", summary?.modes ?? "-", "ti-arrows-transfer-up"],
        ].map(([label, value, icon]) => <article key={label}><i className={`ti ${icon}`} /><div><span>{label}</span><strong>{value}</strong></div></article>)}
      </section>
      <section className="yp-network-grid">
        <article className="yp-data-card yp-carrier-list"><div className="yp-card-heading"><div><h2>운송사 목록</h2><p>등록된 운송사 역량 조회</p></div></div><div className="yp-carrier-items">
          {carriers.map(([id, name]) => <button type="button" key={id} className={selectedCarrier === id ? "active" : ""} onClick={() => setSelectedCarrier(id)}><span className="yp-carrier-symbol">{name.slice(0, 1)}</span><span><b>{name}</b><small>{capabilities.filter((item) => item.carrier_id === id).length}개 서비스</small></span><i className="ti ti-chevron-right" /></button>)}
        </div></article>
        <article className="yp-data-card yp-map-card"><div className="yp-card-heading"><div><h2>글로벌 운송 네트워크</h2><p>운송사별 서비스 구간과 거점</p></div><span className="yp-ready-badge">{summary ? "DATA CONNECTED" : "LOADING"}</span></div><div className="yp-map-placeholder"><div className="yp-map-grid" /><span className="yp-map-node node-one" /><span className="yp-map-node node-two" /><span className="yp-map-node node-three" /><span className="yp-map-route route-one" /><span className="yp-map-route route-two" /><div className="yp-map-message"><i className="ti ti-world-share" /><strong>{visibleCapabilities.length ? `${visibleCapabilities.length}개 경로 미리보기` : "운송 네트워크 영역"}</strong><span>실제 지도 연결은 다음 단계에서 추가합니다.</span></div></div></article>
      </section>
      <section className="yp-data-card yp-service-card"><div className="yp-card-heading"><div><h2>운송 서비스 역량</h2><p>선택한 운송사의 구간별 서비스 정보</p></div></div><div className="yp-live-table"><div className="yp-capability-head"><span>운송사</span><span>운송 모드</span><span>출발지</span><span>도착지</span><span>리드타임</span><span>상태</span></div>
        {visibleCapabilities.map((item) => <div className="yp-capability-row" key={item.capability_id}><span>{item.carrier_name}</span><span>{MODE_LABEL[item.mode] ?? item.mode}</span><span>{item.origin_name}</span><span>{item.destination_name}</span><span>{item.transit_hours ? `${Math.round(item.transit_hours)}h` : "-"}</span><span className={`yp-status ${item.validation_status}`}>{item.validation_status}</span></div>)}
        {!visibleCapabilities.length && <div className="yp-empty-state yp-table-empty"><i className="ti ti-route-off" /><strong>표시할 역량 데이터가 없습니다.</strong></div>}
      </div></section>
    </div>
  );
}

