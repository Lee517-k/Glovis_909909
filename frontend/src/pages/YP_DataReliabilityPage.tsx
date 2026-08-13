import "./YP_data.css";

export function YP_DataReliabilityPage() {
  return (
    <main className="yp-data-page">
      <header className="yp-page-heading yp-data-heading">
        <div>
          <span><i className="ti ti-shield-check" /> DATA QUALITY</span>
          <h1>데이터 신뢰도</h1>
          <p>운송사별 데이터의 완전성, 최신성, 검증 상태를 확인합니다.</p>
        </div>
        <button type="button" disabled><i className="ti ti-refresh" /> 신뢰도 재계산</button>
      </header>

      <section className="yp-reliability-kpis">
        {[
          ["전체 신뢰도", "-", "평가 대기", "ti-shield-check"],
          ["검증 완료", "0", "운송사", "ti-circle-check"],
          ["확인 필요", "0", "항목", "ti-alert-triangle"],
          ["최근 검증", "-", "업데이트 없음", "ti-calendar-check"],
        ].map(([label, value, detail, icon]) => (
          <article key={label}><i className={`ti ${icon}`} /><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>
        ))}
      </section>

      <section className="yp-reliability-layout">
        <article className="yp-data-card yp-quality-list">
          <div className="yp-card-heading"><div><h2>운송사별 신뢰도</h2><p>검증 대상 운송사 목록</p></div></div>
          <div className="yp-empty-state"><i className="ti ti-building-warehouse" /><strong>검증된 운송사가 없습니다.</strong><span>업로드가 완료되면 운송사별 점수가 표시됩니다.</span></div>
        </article>

        <article className="yp-data-card yp-quality-detail">
          <div className="yp-card-heading"><div><h2>신뢰도 상세</h2><p>항목별 품질 평가 결과</p></div><span className="yp-ready-badge">NOT EVALUATED</span></div>
          <div className="yp-quality-score">
            <div className="yp-score-ring"><span>-</span><small>/ 100</small></div>
            <div><strong>평가할 데이터를 선택하세요</strong><p>완전성·정확성·최신성·일관성을 기준으로 평가합니다.</p></div>
          </div>
          <div className="yp-quality-bars">
            {["데이터 완전성", "형식 정확성", "정보 최신성", "필드 일관성"].map((label) => (
              <div key={label}><span>{label}</span><div><i /></div><b>-</b></div>
            ))}
          </div>
        </article>
      </section>

      <section className="yp-data-card">
        <div className="yp-card-heading"><div><h2>검증 항목</h2><p>데이터 오류 및 주의 항목</p></div><button type="button" disabled>전체 상태</button></div>
        <div className="yp-reliability-table">
          <div className="yp-reliability-head"><span>검증 항목</span><span>대상 필드</span><span>심각도</span><span>발견 건수</span><span>상태</span></div>
          <div className="yp-empty-state yp-table-empty"><i className="ti ti-shield-off" /><strong>검증 결과가 없습니다.</strong><span>데이터 검증 후 상세 항목이 표시됩니다.</span></div>
        </div>
      </section>
    </main>
  );
}

