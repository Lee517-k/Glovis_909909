import { useEffect, useRef, useState } from "react";
import type { PageId } from "../types/navigation";
import "./AppHeader.css";

type Insight = {
  insight_id: string;
  severity: string;
  category?: string;
  title: string;
  location?: string;
  action_type: PageId;
  action_label: string;
};

const API = (import.meta.env.VITE_API_BASE_URL ?? "/api").replace(/\/$/, "");

export function AppHeader({ onNavigate }: { onNavigate: (page: PageId) => void }) {
  const [panel, setPanel] = useState<"alerts" | "profile" | null>(null);
  const [accountMode, setAccountMode] = useState(false);
  const [insights, setInsights] = useState<Insight[]>([]);
  const rootRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const load = () => fetch(`${API}/dashboard`).then((response) => response.ok ? response.json() : null)
      .then((data) => setInsights(data?.ai_insights ?? []))
      .catch(() => undefined);
    load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setPanel(null);
        setAccountMode(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const openInsight = (insight: Insight) => {
    onNavigate(insight.action_type);
    setPanel(null);
  };

  return <header className="topbar yp-topbar" ref={rootRef}>
    <div className="spacer" />
    <button className="yp-predicted-risk" onClick={() => onNavigate("dashboard")}>
      <span className="pulse" />예측된 위험 <b>{insights.length}건</b>
    </button>
    <div className="yp-topbar-control">
      <button className={`icobtn ${panel === "alerts" ? "active" : ""}`} aria-label="AI 위험 알림" onClick={() => setPanel((value) => value === "alerts" ? null : "alerts")}>
        <i className="ti ti-bell" />{insights.length > 0 && <span className="yp-alert-count">{insights.length}</span>}
      </button>
      {panel === "alerts" && <div className="yp-topbar-popover yp-alert-popover">
        <div className="yp-popover-head"><div><b>AI 인사이트 · 리스크</b><p>현재 활성화된 예측 위험</p></div><span>{insights.length}건</span></div>
        <div className="yp-alert-items">{insights.map((insight) => <button key={insight.insight_id} onClick={() => openInsight(insight)}>
          <i className={`ti ${insight.category === "PORT_STRIKE" ? "ti-building-factory-2" : insight.category === "FLIGHT_CANCELLATION" ? "ti-plane-off" : insight.category === "WEATHER" ? "ti-cloud-storm" : "ti-route-exclamation"}`} />
          <span><b>{insight.title}</b><small>{insight.location ?? "영향 구간"} · {insight.action_label}</small></span>
          <em className={insight.severity.toLowerCase()}>{insight.severity}</em>
        </button>)}</div>
        <button className="yp-popover-all" onClick={() => { onNavigate("dashboard"); setPanel(null); }}>전체 인사이트 보기<i className="ti ti-arrow-right" /></button>
      </div>}
    </div>
    <div className="yp-topbar-control">
      <button className={`yp-avatar ${panel === "profile" ? "active" : ""}`} aria-label="사용자 및 로그인 관리" onClick={() => setPanel((value) => value === "profile" ? null : "profile")}>KR<i className="ti ti-chevron-down" /></button>
      {panel === "profile" && <div className="yp-topbar-popover yp-profile-popover">
        {!accountMode ? <>
          <div className="yp-profile-user"><span>KR</span><div><b>Control Tower 운영자</b><p>controltower@glovis.com</p></div></div>
          <div className="yp-login-status"><span className="pulse" />로그인됨<small>관리자 권한</small></div>
          <div className="yp-profile-menu">
            <button onClick={() => setAccountMode(true)}><i className="ti ti-user-cog" /><span><b>계정 및 로그인 관리</b><small>프로필 정보와 세션 설정</small></span><i className="ti ti-chevron-right" /></button>
            <button><i className="ti ti-shield-lock" /><span><b>보안 설정</b><small>비밀번호 및 2단계 인증</small></span><i className="ti ti-chevron-right" /></button>
          </div>
          <button className="yp-logout"><i className="ti ti-logout" />로그아웃</button>
        </> : <div className="yp-account-panel">
          <button className="yp-account-back" onClick={() => setAccountMode(false)}><i className="ti ti-arrow-left" />계정 및 로그인 관리</button>
          <label>표시 이름<input defaultValue="Control Tower 운영자" /></label>
          <label>이메일<input type="email" defaultValue="controltower@glovis.com" /></label>
          <label>권한<select defaultValue="admin"><option value="admin">관리자</option><option value="operator">운영자</option><option value="viewer">조회 전용</option></select></label>
          <div className="yp-session-info"><i className="ti ti-device-desktop" /><span><b>현재 세션</b><small>Windows · 서울 · 활성</small></span></div>
          <button className="btn primary" onClick={() => setAccountMode(false)}>변경사항 저장</button>
        </div>}
      </div>}
    </div>
  </header>;
}
