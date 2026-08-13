import { useEffect, useMemo, useState } from "react";

import { getYPReliability, type YPReliability } from "../api/YP_dataApi";
import "./YP_data.css";

export function YP_DataReliabilityPage() {
  const [items, setItems] = useState<YPReliability[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { getYPReliability().then((data) => { setItems(data.items); setSelectedId(data.items[0]?.carrier_id ?? ""); }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : "조회 실패")); }, []);
  const selected = items.find((item) => item.carrier_id === selectedId);
  const totals = useMemo(() => ({ verified: items.reduce((sum, item) => sum + item.verified_count, 0), review: items.reduce((sum, item) => sum + item.review_count, 0), average: items.length ? Math.round(items.reduce((sum, item) => sum + item.score, 0) / items.length) : 0 }), [items]);

  return <main className="yp-data-page">
    {error && <div className="yp-api-error">{error} 백엔드 실행 상태를 확인해주세요.</div>}
    <section className="yp-reliability-kpis">{[["평균 신뢰도", items.length ? totals.average : "-", "점", "ti-shield-check"],["검증 완료", totals.verified, "건", "ti-circle-check"],["확인 필요", totals.review, "건", "ti-alert-triangle"],["등록 운송사", items.length || "-", "개", "ti-building-warehouse"]].map(([label,value,detail,icon])=><article key={label}><i className={`ti ${icon}`} /><div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div></article>)}</section>
    <section className="yp-reliability-layout"><article className="yp-data-card yp-quality-list"><div className="yp-card-heading"><div><h2>운송사별 신뢰도</h2><p>검증 대상 운송사 목록</p></div></div><div className="yp-reliability-carriers">{items.map((item)=><button type="button" className={selectedId===item.carrier_id?"active":""} key={item.carrier_id} onClick={()=>setSelectedId(item.carrier_id)}><span><b>{item.carrier_name}</b><small>{item.capability_count}개 역량</small></span><strong>{item.score || 0}</strong></button>)}</div></article>
      <article className="yp-data-card yp-quality-detail"><div className="yp-card-heading"><div><h2>신뢰도 상세</h2><p>{selected?.carrier_name ?? "항목별 품질 평가 결과"}</p></div><span className="yp-ready-badge">{selected ? "DATA CONNECTED" : "NOT EVALUATED"}</span></div><div className="yp-quality-score"><div className="yp-score-ring"><span>{selected?.score ?? "-"}</span><small>/ 100</small></div><div><strong>{selected ? `${selected.carrier_name} 평가 현황` : "평가할 데이터를 선택하세요"}</strong><p>검증 완료 {selected?.verified_count ?? 0}건 · 확인 필요 {selected?.review_count ?? 0}건</p></div></div><div className="yp-quality-bars">{["데이터 완전성","형식 정확성","정보 최신성","필드 일관성"].map((label,index)=>{const score=Math.max(0,(selected?.score ?? 0)-index*4);return <div key={label}><span>{label}</span><div><i style={{width:`${score}%`}} /></div><b>{selected?score:"-"}</b></div>})}</div></article></section>
    <section className="yp-data-card"><div className="yp-card-heading"><div><h2>검증 항목</h2><p>운송사별 검증 요약</p></div></div><div className="yp-reliability-table"><div className="yp-reliability-head"><span>운송사</span><span>전체 역량</span><span>평균 점수</span><span>확인 필요</span><span>상태</span></div>{items.slice(0,10).map((item)=><div className="yp-reliability-row" key={item.carrier_id}><span>{item.carrier_name}</span><span>{item.capability_count}</span><span>{item.score}</span><span>{item.review_count}</span><span>{item.review_count?"검토 필요":"검증 완료"}</span></div>)}</div></section>
  </main>;
}
