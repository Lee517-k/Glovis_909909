import { useEffect, useRef, useState } from "react";
import type { NegotiationEvent } from "../../types/negotiation";

function formatElapsed(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}분 ${s.toString().padStart(2, "0")}초`;
}

const STAGE_LABEL: Record<string, string> = {
  route_search: "경로 탐색",
  ranking: "순위 산정",
  complete: "완료 처리",
};

function eventIcon(ev: NegotiationEvent): string {
  if (ev.stage === "route_search") return "ti-route";
  if (ev.stage === "ranking") return "ti-list-numbers";
  if (ev.stage === "complete") return "ti-flag-check";
  return "ti-point";
}

export function NegotiationConsole({
  status,
  progress,
  stage,
  message,
  events,
  startedAt,
}: {
  status: "PROCESSING" | "COMPLETED" | "FAILED";
  progress: number;
  stage: string;
  message: string;
  events: NegotiationEvent[];
  startedAt: string;
}) {
  const feedRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [events.length]);

  useEffect(() => {
    if (status !== "PROCESSING") return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [status]);

  const startedMs = startedAt ? new Date(startedAt).getTime() : now;
  const elapsed = formatElapsed(now - startedMs);

  return (
    <div className="coord" style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <h4>
            <i className="ti ti-topology-star-3" />
            규칙 기반 경로 탐색 · {STAGE_LABEL[stage] ?? stage}
          </h4>
          <div className="cs">{message || "대기 중..."}</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: 28, fontWeight: 750, letterSpacing: -1 }}>{Math.round(progress)}%</div>
          <div style={{ fontSize: 9.5, letterSpacing: ".12em", textTransform: "uppercase", color: "rgba(255,255,255,.55)", fontWeight: 700 }}>
            {status === "PROCESSING" ? "Searching" : status === "COMPLETED" ? "Done" : "Failed"}
          </div>
        </div>
      </div>
      <div className="cbar">
        <i style={{ width: `${progress}%`, background: status === "FAILED" ? "#D8443C" : undefined }} />
      </div>
      {status === "PROCESSING" && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "rgba(255,255,255,.65)", margin: "8px 0 4px" }}>
          <i className="ti ti-clock" />
          경과 {elapsed} · LLM 협상 없이 결정론적으로 계산해서 보통 1초 안에 끝납니다.
        </div>
      )}
      <div className="cgrid">
        <div className="cbox" style={{ gridColumn: "span 3" }}>
          <h6>
            <i className="ti ti-activity" />
            탐색 로그 ({events.length}건)
          </h6>
          <div ref={feedRef} style={{ maxHeight: 260, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6, paddingRight: 4 }}>
            {events.length === 0 && <div className="coordwait">탐색 시작을 기다리는 중입니다…</div>}
            {events.map((ev, i) => (
              <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 12.5, color: "rgba(255,255,255,.85)" }}>
                <i className={`ti ${eventIcon(ev)}`} style={{ marginTop: 2, opacity: 0.75, flexShrink: 0 }} />
                <span>{ev.message}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
