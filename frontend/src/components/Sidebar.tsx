import type { PageId } from "../types/navigation";

const NAV: {
  group: string;
  items: { id: PageId; icon: string; label: string }[];
}[] = [
  {
    group: "Overview",
    items: [{ id: "dashboard", icon: "ti-layout-dashboard", label: "대시보드" }],
  },
  {
    group: "Decision",
    items: [
      { id: "scenario", icon: "ti-hierarchy-2", label: "운송 시나리오" },
      { id: "saved", icon: "ti-folder", label: "제안서 보관함" },
    ],
  },
  {
    group: "Execution",
    items: [
      { id: "tracking", icon: "ti-route", label: "운송 추적" },
      { id: "network", icon: "ti-world-share", label: "운송사 배분" },
    ],
  },
  {
    group: "Data",
    items: [
      { id: "upload", icon: "ti-cloud-upload", label: "데이터" },
      { id: "yp_data_reliability", icon: "ti-shield-check", label: "데이터 신뢰도" },
    ],
  },
];

interface SidebarProps {
  page: PageId;
  onNavigate: (page: PageId) => void;
  savedCount: number;
  trackingCount: number;
}

export function Sidebar({ page, onNavigate, savedCount, trackingCount }: SidebarProps) {
  const counts: Partial<Record<PageId, number>> = {
    saved: savedCount,
    tracking: trackingCount,
  };

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brandmark">G</div>
        <div>
          <h1>GLOVIS</h1>
          <p>AI Control Tower</p>
        </div>
      </div>

      {NAV.map((group) => (
        <div className="navgrp" key={group.group}>
          <label>{group.group}</label>
          {group.items.map((item) => (
            <button
              key={item.id}
              className={`navbtn ${page === item.id ? "active" : ""}`}
              type="button"
              title={item.label}
              onClick={() => onNavigate(item.id)}
            >
              <i className={`ti ${item.icon}`} />
              <span>{item.label}</span>
              {counts[item.id] !== undefined && <span className="cnt">{counts[item.id]}</span>}
            </button>
          ))}
        </div>
      ))}

      <div className="navfoot">
        <span className="pulse" />
        Agent Engine Online
        <br />8 Agents · Coordinator v1
      </div>
    </aside>
  );
}

