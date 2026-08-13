const CARRIERS = ["현대글로비스", "Maersk", "Hapag-Lloyd", "Korean Air Cargo"];

export function YP_CarrierVisualizationPanel() {
  return (
    <div className="yp-network-shell">
      <section className="yp-network-toolbar">
        <div className="yp-searchbox">
          <i className="ti ti-search" aria-hidden="true" />
          <span>운송사 또는 서비스 검색</span>
        </div>
        <button type="button" disabled>
          <i className="ti ti-adjustments-horizontal" /> 필터
        </button>
      </section>

      <section className="yp-network-kpis">
        {[
          ["등록 운송사", "-", "ti-building-warehouse"],
          ["운송 서비스", "-", "ti-route"],
          ["연결 국가", "-", "ti-world"],
          ["운송 모드", "4", "ti-arrows-transfer-up"],
        ].map(([label, value, icon]) => (
          <article key={label}>
            <i className={`ti ${icon}`} aria-hidden="true" />
            <div><span>{label}</span><strong>{value}</strong></div>
          </article>
        ))}
      </section>

      <section className="yp-network-grid">
        <article className="yp-data-card yp-carrier-list">
          <div className="yp-card-heading">
            <div><h2>운송사 목록</h2><p>등록된 운송사 역량 조회</p></div>
          </div>
          <div className="yp-carrier-items">
            {CARRIERS.map((carrier, index) => (
              <button type="button" key={carrier} className={index === 0 ? "active" : ""}>
                <span className="yp-carrier-symbol">{carrier.slice(0, 1)}</span>
                <span><b>{carrier}</b><small>역량 데이터 준비 중</small></span>
                <i className="ti ti-chevron-right" />
              </button>
            ))}
          </div>
        </article>

        <article className="yp-data-card yp-map-card">
          <div className="yp-card-heading">
            <div><h2>글로벌 운송 네트워크</h2><p>운송사별 서비스 구간과 거점</p></div>
            <span className="yp-ready-badge">DATA READY</span>
          </div>
          <div className="yp-map-placeholder">
            <div className="yp-map-grid" aria-hidden="true" />
            <span className="yp-map-node node-one" />
            <span className="yp-map-node node-two" />
            <span className="yp-map-node node-three" />
            <span className="yp-map-route route-one" />
            <span className="yp-map-route route-two" />
            <div className="yp-map-message">
              <i className="ti ti-world-share" />
              <strong>운송 네트워크 영역</strong>
              <span>데이터 연동 후 실제 경로가 표시됩니다.</span>
            </div>
          </div>
        </article>
      </section>

      <section className="yp-data-card yp-service-card">
        <div className="yp-card-heading">
          <div><h2>운송 서비스 역량</h2><p>선택한 운송사의 구간별 서비스 정보</p></div>
        </div>
        <div className="yp-capability-table">
          <div className="yp-capability-head"><span>운송사</span><span>운송 모드</span><span>출발지</span><span>도착지</span><span>리드타임</span><span>상태</span></div>
          <div className="yp-empty-state yp-table-empty"><i className="ti ti-route-off" /><strong>표시할 역량 데이터가 없습니다.</strong><span>승인된 데이터가 이 영역에 표시됩니다.</span></div>
        </div>
      </section>
    </div>
  );
}

