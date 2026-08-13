import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTrackingKpis, getShipmentOverview, searchShipments } from "../api/HS_controlTowerApi";
import { RouteMapLibre } from "../components/RouteMapLibre";
import { Badge, Chip, Kpi, Prog, type Mode } from "../lib/ui";

const JICON = ["ti-anchor", "ti-plane", "ti-file-check", "ti-truck", "ti-building-warehouse"];
type Scope = "all" | "active" | "completed" | "planned";
type Sort = "eta" | "-eta" | "name" | "-name" | "progress" | "-progress";

export function TrackingPage({ active }: { active: boolean }) {
  const [view, setView] = useState<"map" | "list">("map");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchText, setSearchText] = useState("");
  const [query, setQuery] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [scope, setScope] = useState<Scope>("all");
  const [status, setStatus] = useState("");
  const [transportMode, setTransportMode] = useState("");
  const [etaFrom, setEtaFrom] = useState("");
  const [etaTo, setEtaTo] = useState("");
  const [sort, setSort] = useState<Sort>("eta");
  const filterRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQuery(searchText.trim()), 250);
    return () => clearTimeout(timer);
  }, [searchText]);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (filterRef.current && !filterRef.current.contains(event.target as Node)) setShowFilter(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const { data: kpis } = useQuery({ queryKey: ["tracking-kpis"], queryFn: getTrackingKpis });
  const { data: shipmentsResp, isFetching } = useQuery({
    queryKey: ["tracking-shipments", query, scope, status, transportMode, etaFrom, etaTo, sort],
    queryFn: () => searchShipments({
      q: query, scope, status, mode: transportMode, eta_from: etaFrom, eta_to: etaTo, sort, limit: 200,
    }),
  });
  const shipments = shipmentsResp?.items ?? [];
  const activeId = shipments.some((s) => s.id === selectedId) ? selectedId : shipments[0]?.id ?? null;
  const { data: overview } = useQuery({
    queryKey: ["tracking-overview", activeId],
    queryFn: () => getShipmentOverview(activeId as string),
    enabled: !!activeId,
  });
  const detail = overview?.detail;
  const steps = overview?.segments.steps ?? [];

  const toggleEtaSort = () => setSort((current) => current === "eta" ? "-eta" : "eta");
  const resetFilters = () => {
    setScope("all"); setStatus(""); setTransportMode(""); setEtaFrom(""); setEtaTo(""); setSort("eta");
  };
  const filterCount = [scope !== "all", !!status, !!transportMode, !!etaFrom, !!etaTo].filter(Boolean).length;
  const kpiActive = (index: number) =>
    (index === 0 && scope === "active" && !status) ||
    (index === 1 && status === "DELAYED") ||
    (index === 2 && status === "AT_RISK") ||
    (index === 3 && status === "ARRIVING_TODAY") ||
    (index === 4 && status === "TRANSSHIP_WAIT");
  const applyKpi = (index: number) => {
    if (kpiActive(index)) {
      setScope("all");
      setStatus("");
      return;
    }
    setScope("active");
    setStatus(["", "DELAYED", "AT_RISK", "ARRIVING_TODAY", "TRANSSHIP_WAIT"][index] ?? "");
  };

  const shipmentCard = (s: (typeof shipments)[number]) => (
    <button className={`tracking-shipment ${s.id === activeId ? "active" : ""}`} key={s.id} onClick={() => setSelectedId(s.id)}>
      <div className="tracking-shipment-head"><b className="mono">{s.id}</b><Badge tone={s.st[0]}>{s.st[1]}</Badge></div>
      <strong>{s.lane}</strong>
      <div className="tracking-shipment-modes">
        {s.modes.map((m) => <Chip key={m} mode={m as Mode} />)}
        <span>{s.cargo}</span>
      </div>
      <div className={`tracking-shipment-progress ${s.pct === 100 ? "completed" : ""}`}><Prog pct={s.pct} /><span>{s.pct}%</span></div>
      <div className="tracking-shipment-eta"><span>{s.status_label}</span><b>ETA {s.eta.replace("T", " ")}</b></div>
    </button>
  );

  return (
    <section id="tracking" className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div><div className="eyebrow"><i className="ti ti-route" />Shipment Execution</div><h3>운송 추적</h3><p>전체 화물의 경로와 ETA, 구간별 진행 상태를 실시간으로 확인합니다.</p></div>
        <div className="hactions"><div className="toggle">
          <button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>지도</button>
          <button className={view === "list" ? "active" : ""} onClick={() => setView("list")}>목록</button>
        </div></div>
      </div>

      <div className="grid kpis tracking-kpis">
        {kpis?.cards.map((card, index) => <Kpi key={card.label} icon={card.icon} label={card.label} value={card.value} unit={card.unit} sub={card.sub} tone={card.tone ?? undefined} active={kpiActive(index)} onClick={() => applyKpi(index)} />)}
      </div>

      <section className="card tracking-workspace">
        <div className="tracking-toolbar">
          <div className="tracking-search"><i className="ti ti-search" /><input aria-label="화물 검색" placeholder="운송번호, 화물명, 출발지, 도착지, 운송사 검색" value={searchText} onChange={(e) => setSearchText(e.target.value)} />{searchText && <button aria-label="검색어 지우기" onClick={() => setSearchText("")}><i className="ti ti-x" /></button>}</div>
          <div className="tracking-filter-anchor" ref={filterRef}>
            <button className={`btn ${filterCount ? "active" : ""}`} onClick={() => setShowFilter((value) => !value)}><i className="ti ti-filter" />필터{filterCount > 0 && <span className="filter-count">{filterCount}</span>}</button>
            {showFilter && <div className="tracking-filter-panel card">
              <div className="tracking-filter-title"><div><b>화물 필터</b><p>조건은 백엔드 목록에 바로 적용됩니다.</p></div><button onClick={resetFilters}>초기화</button></div>
              <label>운송 상태<select value={scope} onChange={(e) => setScope(e.target.value as Scope)}><option value="all">전체</option><option value="active">진행 중</option><option value="planned">운송 예정</option><option value="completed">운송 완료</option></select></label>
              <label>상세 상태<select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">전체</option><option value="DELAYED">지연</option><option value="AT_RISK">리스크 감시</option></select></label>
              <label>운송 모드<select value={transportMode} onChange={(e) => setTransportMode(e.target.value)}><option value="">전체</option><option value="sea">해상</option><option value="air">항공</option><option value="rail">철도</option><option value="road">육상</option></select></label>
              <div className="tracking-date-range"><label>ETA 시작<input type="date" value={etaFrom} onChange={(e) => setEtaFrom(e.target.value)} /></label><label>ETA 종료<input type="date" value={etaTo} min={etaFrom} onChange={(e) => setEtaTo(e.target.value)} /></label></div>
              <label>정렬<select value={sort} onChange={(e) => setSort(e.target.value as Sort)}><option value="eta">ETA 빠른 순</option><option value="-eta">ETA 늦은 순</option><option value="name">노선 이름 오름차순</option><option value="-name">노선 이름 내림차순</option><option value="-progress">진행률 높은 순</option><option value="progress">진행률 낮은 순</option></select></label>
            </div>}
          </div>
          <button className="btn" onClick={toggleEtaSort} title="ETA 오름차순/내림차순 전환"><i className={`ti ${sort === "-eta" ? "ti-sort-descending" : "ti-sort-ascending"}`} />ETA {sort === "-eta" ? "늦은 순" : "빠른 순"}</button>
          <span className="pill"><i className={`ti ${isFetching ? "ti-loader-2" : "ti-clock"}`} />{isFetching ? "갱신 중" : `${shipmentsResp?.total ?? 0}건`}</span>
        </div>

        {view === "map" ? <>
          <div className="tracking-map-detail-grid">
          <div className="tracking-map-pane tracking-map-card">
            <RouteMapLibre route={overview?.route} />
            <div className="journey tracking-journey"><div className="jt">Multimodal Journey Timeline</div><div className="jsteps">{steps.map((step, index) => <div className={`jstep ${step.state}`} key={step.sequence}><div className="d"><i className={`ti ${JICON[index % JICON.length]}`} /></div><b>{step.short || step.t.split(" → ").pop()}</b><span>{step.a || step.p}</span></div>)}</div></div>
          </div>
          <aside className="tracking-intermodal-card">
            <div className="card-hd"><div><span className="badge b-blue">INTERMODAL</span><h4>{detail?.shipmentId}</h4><p>{detail?.cargo}</p></div></div>
            <div className="card-bd tracking-intermodal-body">
              <div className="tracking-detail-grid"><div><span>리스크</span><b>{detail?.riskLabel}</b></div><div><span>탄소 등급</span><b>{detail?.co2Label}</b></div><div><span>현재 위치</span><b>{detail?.location}</b></div><div><span>ETA</span><b>{detail?.eta.replace("T", " ")}</b></div></div>
              <div className="summarykv"><span>운송사</span><b>{detail?.carrierLabel}</b></div>
              {detail?.alert && <div className="aialert"><div className="h"><i className="ti ti-alert-triangle-filled" />AI 알림</div><p>{detail.alert}</p></div>}
              <button className="btn primary tracking-full-button"><i className="ti ti-route-2" />대안 경로 분석</button>
              <div className="tracking-detail-actions"><button className="btn"><i className="ti ti-mail" />운송사 연락</button><button className="btn"><i className="ti ti-file-text" />서류</button></div>
            </div>
          </aside></div>
          <section className="tracking-table-section">
            <div className="tracking-table-head"><div><h4>화물 목록</h4><p>{shipmentsResp?.total ?? 0}건 · 행을 선택하면 지도와 인터모달 정보가 변경됩니다.</p></div></div>
            <div className="tablewrap tracking-table-wrap"><table><thead><tr><th>운송번호</th><th>구간</th><th>모드</th><th>현재 위치</th><th>진행률</th><th>ETA</th><th>상태</th></tr></thead><tbody>{shipments.map((s) => <tr key={s.id} className={s.id === activeId ? "selected" : ""} onClick={() => setSelectedId(s.id)}><td><b className="mono">{s.id}</b><div className="sub2">{s.cargo}</div></td><td>{s.lane}</td><td className="mode-cell">{s.modes.map((m) => <Chip key={m} mode={m as Mode} />)}</td><td>{s.loc}</td><td><div className={`tracking-table-progress ${s.pct === 100 ? "completed" : ""}`}><Prog pct={s.pct} /><span>{s.pct}%</span></div></td><td className="mono">{s.eta.replace("T", " ")}</td><td><Badge tone={s.st[0]}>{s.st[1]}</Badge></td></tr>)}</tbody></table></div>
          </section>
        </> : <div className="tracking-list-view"><div className="tracking-list-column"><div className="tracking-side-title"><div><h4>전체 화물 목록</h4><p>{shipmentsResp?.total ?? 0}건</p></div></div>{shipments.map(shipmentCard)}</div><section className="tracking-segments"><h4>구간 진행</h4><p>{detail?.shipmentId} · 계획 대비 실적</p>{steps.map((step, index) => <div className={`segment ${step.state}`} key={step.sequence}><div className="rail"><div className="d">{step.state === "done" ? <i className="ti ti-check" /> : index + 1}</div>{index < steps.length - 1 && <div className="line" />}</div><div className="ct"><div><b>{step.t}</b><p>{step.s}</p></div><div className="rt">{step.p}{step.a && <><br /><span>{step.a}</span></>}</div></div></div>)}</section></div>}
      </section>
    </section>
  );
}
