import type { ReactNode } from "react";

export type Mode = "sea" | "air" | "rail" | "truck" | "express";

export const MODE_KO: Record<Mode, string> = { sea: "해상", air: "항공", rail: "철도", truck: "육상", express: "특송" };
export const MODE_HEX: Record<Mode, string> = {
  sea: "#1687D9",
  air: "#8559D9",
  rail: "#15966F",
  truck: "#D98200",
  express: "#D8443C",
};
export const GRADE_HEX: Record<string, string> = { A: "#0E9E62", B: "#7CB342", C: "#E0A21B", D: "#F07B26", E: "#D8443C" };

const nf = new Intl.NumberFormat("ko-KR");
export const n = (v: number) => nf.format(Math.round(v));
export const krw = (v: number) => `${n(v)}원`;
export const usd = (v: number) => `$${n(v)}`;

export function Chip({ mode }: { mode: Mode }) {
  return <span className={`chip c-${mode}`}>{MODE_KO[mode]}</span>;
}

export function Chips({ modes }: { modes: Mode[] }) {
  return (
    <>
      {modes.map((m, i) => (
        <span key={i}>
          {i > 0 && <span className="sep">›</span>}
          <Chip mode={m} />
        </span>
      ))}
    </>
  );
}

export type BadgeTone = "ok" | "warn" | "danger" | "blue" | "gray" | "purple";

export function Badge({ tone, children, icon }: { tone: BadgeTone; children: ReactNode; icon?: string }) {
  return (
    <span className={`badge b-${tone}`}>
      {icon && <i className={`ti ${icon}`} />}
      {children}
    </span>
  );
}

export function Grade({ value, k }: { value: string; k: string }) {
  return (
    <span className="grade">
      <i style={{ background: GRADE_HEX[value] ?? "#8E9BAF" }}>{value}</i>
      <em>{k.toUpperCase()}</em>
    </span>
  );
}

export function Kpi({
  icon, label, value, unit, sub, tone, onClick, active,
}: {
  icon: string; label: string; value: ReactNode; unit?: string; sub?: string; tone?: string;
  onClick?: () => void; active?: boolean;
}) {
  const subTone = sub && sub[0] === "u" ? "up" : sub && sub[0] === "d" ? "down" : "";
  const subText = sub ? sub.slice(1) : "";
  return (
    <div
      className={`card kpi${active ? " active" : ""}`}
      onClick={onClick}
      style={onClick ? { cursor: "pointer", outline: active ? "2px solid var(--blue)" : undefined } : undefined}
    >
      <div className="lb">
        <span className="ic" style={tone ? { background: `${tone}22`, color: tone } : undefined}>
          <i className={`ti ${icon}`} />
        </span>
        {label}
      </div>
      <div className="vl" style={tone ? { color: tone } : undefined}>
        {value}
        {unit && <small>{unit}</small>}
      </div>
      <div className={`sub ${subTone}`}>
        {sub && (
          <>
            <i className={`ti ${subTone === "up" ? "ti-trending-up" : subTone === "down" ? "ti-trending-down" : ""}`} />
            {subText}
          </>
        )}
      </div>
    </div>
  );
}

export function Prog({ pct }: { pct: number }) {
  return (
    <div className="prog">
      <i style={{ width: `${pct}%` }} />
    </div>
  );
}
