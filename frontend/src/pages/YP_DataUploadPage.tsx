import { useState } from "react";

import { YP_CarrierVisualizationPanel } from "./YP_CarrierVisualizationPanel";
import "./YP_data.css";

type DataTab = "upload" | "network";

export function YP_DataUploadPage() {
  const [tab, setTab] = useState<DataTab>("upload");

  return (
    <main className="yp-data-page">
      <nav className="yp-data-tabs" aria-label="데이터 화면 탭">
        <button className={tab === "upload" ? "active" : ""} type="button" onClick={() => setTab("upload")}>
          <i className="ti ti-upload" /> 데이터 업로드
        </button>
        <button className={tab === "network" ? "active" : ""} type="button" onClick={() => setTab("network")}>
          <i className="ti ti-chart-dots-3" /> 운송사 역량 가시화
        </button>
      </nav>

      {tab === "network" ? <YP_CarrierVisualizationPanel /> : <YP_UploadPanel />}
    </main>
  );
}

function YP_UploadPanel() {
  return (
    <>
      <section className="yp-upload-flow">
        {[
          ["원본 파일 업로드", "xlsx · csv · pdf"],
          ["검증 및 확인", "오류·경고 항목 확인"],
          ["DB 반영", "승인된 역량 저장"],
        ].map(([title, detail], index) => (
          <article className={index === 0 ? "active" : ""} key={title}>
            <span>{index + 1}</span><div><b>{title}</b><small>{detail}</small></div>
          </article>
        ))}
      </section>

      <section className="yp-upload-layout">
        <article className="yp-data-card">
          <div className="yp-card-heading">
            <div><h2>운송사 역량 원본 업로드</h2><p>제공된 템플릿 또는 표가 포함된 파일을 업로드하세요.</p></div>
            <span className="yp-required-badge">선사명 필수</span>
          </div>
          <div className="yp-upload-body">
            <label>선사 이름 <em>필수</em></label>
            <div className="yp-carrier-input"><i className="ti ti-building-warehouse" /><span>예: 현대글로비스</span></div>
            <small>입력한 이름은 운송사 식별자로 사용됩니다.</small>

            <div className="yp-upload-box">
              <div className="yp-upload-icon"><i className="ti ti-cloud-upload" /></div>
              <h2>분석할 파일을 여기에 놓으세요</h2>
              <p>xlsx · csv · pdf · 최대 20MB</p>
              <button type="button">파일 선택</button>
            </div>
            <p className="yp-upload-notice">분석 단계에서는 데이터베이스가 변경되지 않습니다.</p>
          </div>
        </article>

        <aside className="yp-data-card yp-upload-guide">
          <div className="yp-card-heading"><div><h2>업로드 처리 원칙</h2><p>데이터 등록 전 확인 사항</p></div></div>
          <ul>
            {[
              ["ti-table", "Excel 컬럼 매핑", "원본 헤더를 시스템 필드로 변환합니다."],
              ["ti-file-type-pdf", "PDF 표 추출", "표 구조가 확인되는 문서만 분석합니다."],
              ["ti-shield-check", "행 단위 검증", "필수값과 숫자 범위를 검사합니다."],
              ["ti-database-plus", "승인 후 반영", "검토된 데이터만 저장합니다."],
            ].map(([icon, title, detail]) => (
              <li key={title}><i className={`ti ${icon}`} /><span><b>{title}</b><small>{detail}</small></span></li>
            ))}
          </ul>
        </aside>
      </section>
    </>
  );
}
