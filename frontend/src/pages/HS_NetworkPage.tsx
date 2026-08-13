import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAllocationOverview, getRegions, carriersCsvUrl } from "../api/controlTowerApi";
import { HubMapLibre } from "../components/HubMapLibre";
import { Badge, Chip, Grade, MODE_HEX, MODE_KO, Prog, type Mode } from "../lib/ui";

export function NetworkPage({ active }: { active: boolean }) {
  const [regionId, setRegionId] = useState<string | null>(null);

  const { data: regions } = useQuery({ queryKey: ["allocation-regions"], queryFn: getRegions });
  const { data: overview } = useQuery({
    queryKey: ["allocation-overview", regionId],
    queryFn: () => getAllocationOverview(regionId ?? undefined),
  });

  const tabs = regions?.tabs ?? [];
  const bubbles = overview?.hubs.bubbles ?? [];
  const allocations = overview?.allocations.allocations ?? [];
  const carriers = overview?.carriers.items ?? [];

  return (
    <section id="network" className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div>
          <div className="eyebrow">
            <i className="ti ti-world-share" />
            Carrier Allocation
          </div>
          <h3>지역권 운송사 배분</h3>
          <p>거점별 물량, 운송사 집중도(HHI), 계약 잔량을 비교합니다.</p>
        </div>
        <div className="hactions">
          <span className="pill">
            <i className="ti ti-calendar" />
            2026 Q2 · 최근 90일
          </span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 7, marginBottom: 14, flexWrap: "wrap" }}>
        {tabs.map((t) => (
          <button
            key={t.region_id ?? "all"}
            className={`btn ${regionId === t.region_id ? "primary" : ""}`}
            onClick={() => setRegionId(t.region_id)}
          >
            {t.region_name}
          </button>
        ))}
      </div>

      <div className="grid netgrid" style={{ marginBottom: 14 }}>
        <section className="card network-map-card">
          <div className="card-hd">
            <div>
              <h4>거점별 물량</h4>
              <p>버블 크기 = 물량 · 색 = 주력 모드</p>
            </div>
          </div>
          <HubMapLibre bubbles={bubbles} />
          <div className="mapfoot">
            {(["sea", "rail", "air", "truck"] as Mode[]).map((m) => (
              <label key={m}>
                <span className="sw" style={{ background: MODE_HEX[m] }} />
                {MODE_KO[m]} 주력
              </label>
            ))}
            <span style={{ marginLeft: "auto", color: "var(--faint)" }}>버블 크기 = 90일 누적 물량</span>
          </div>
        </section>
        <section className="card network-allocation-card">
          <div className="card-hd">
            <div>
              <h4>지역권 × 운송사 배분</h4>
              <p>HHI = 허핀달 집중도 지수</p>
            </div>
          </div>
          <div className="card-bd">
            {allocations.map((a) => (
              <div style={{ marginBottom: 18 }} key={a.region_id}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                  <b style={{ fontSize: 13 }}>{a.rg}</b>
                  <span className="mono" style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--faint)" }}>
                    {a.meta}
                  </span>
                </div>
                <div className="allocbar">
                  {a.cs.map(([nm, pct, c]) => (
                    <span key={nm} style={{ width: `${pct}%`, background: c }}>
                      {pct >= 12 ? `${nm} ${pct}%` : `${pct}%`}
                    </span>
                  ))}
                </div>
                <div style={{ fontSize: 11, color: a.wt === "danger" ? "var(--danger)" : a.wt === "warn" ? "#96610A" : "var(--faint)" }}>
                  {a.wt && <i className="ti ti-alert-triangle-filled" />} {a.hhi}
                  {a.warn}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card">
        <div className="card-hd">
          <div>
            <h4>운송사 현황</h4>
            <p>해상만 CII · 나머지 ESG 등급</p>
          </div>
          <div className="spacer" />
          <a className="btn sm" href={carriersCsvUrl(regionId ?? undefined)} download>
            <i className="ti ti-download" />
            CSV
          </a>
        </div>
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th>운송사</th>
                <th>모드</th>
                <th>주력 지역권</th>
                <th className="r">물량</th>
                <th className="r">집행액</th>
                <th className="r">비중</th>
                <th className="r">정시율</th>
                <th>탄소 등급</th>
                <th className="r">계약 잔량</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {carriers.map((c) => (
                <tr key={c.carrier_id}>
                  <td>
                    <div style={{ fontWeight: 700 }}>{c.n}</div>
                    <div className="sub2">{c.sub}</div>
                  </td>
                  <td>
                    {c.m.map((m) => (
                      <Chip key={m} mode={m as Mode} />
                    ))}
                  </td>
                  <td style={{ fontSize: 12 }}>{c.rg}</td>
                  <td className="r num">{c.v}</td>
                  <td className="r num">{c.sp}</td>
                  <td className="r">
                    <div style={{ display: "flex", alignItems: "center", gap: 7, justifyContent: "flex-end" }}>
                      <b className="num">{c.sh}%</b>
                      <div style={{ width: 46 }}>
                        <Prog pct={c.sh} />
                      </div>
                    </div>
                  </td>
                  <td className="r num">{c.ot}%</td>
                  <td>
                    <Grade value={c.g} k={c.gk} />
                  </td>
                  <td className="r num">{c.cr}</td>
                  <td>
                    <Badge tone={c.st[0]}>{c.st[1]}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
