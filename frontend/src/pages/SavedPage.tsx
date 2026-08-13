import { useState } from "react";
import { Badge, type BadgeTone } from "../lib/YP_ui";
import type { SavedScenario } from "../types/negotiation";
import "./YP_glovis_primitives.css";

export interface SavedProposal {
  id: string;
  title: string;
  cost: string;
  days: string;
  grade: string;
  when: string;
  tag: BadgeTone;
  tagLabel: string;
  isFavorite: boolean;
}

export function SavedPage({
  active,
  items,
  unsaved,
  onUnbookmark,
  onAddToBookmark,
  onOpen,
}: {
  active: boolean;
  items: SavedProposal[];
  unsaved: SavedScenario[];
  onUnbookmark: (scenarioId: string) => void;
  onAddToBookmark: (scenarioId: string) => void;
  onOpen: (scenarioId: string, status: string) => void;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <section id="saved" className={`page ${active ? "active" : ""}`}>
      <div className="phead">
        <div>
          <div className="eyebrow">
            <i className="ti ti-folder" />
            Decision · Saved
          </div>
          <h3>제안서 보관함</h3>
          <p>확정 전 제안을 저장해 두고 언제든 다시 열어 비교할 수 있습니다.</p>
        </div>
        <div className="hactions">
          <span className="pill">
            <i className="ti ti-folder" />
            {items.length}건 저장
          </span>
          <button className="btn blue" onClick={() => setPickerOpen(true)}>
            <i className="ti ti-plus" />
            제안서 저장 ({unsaved.length}건 대기)
          </button>
        </div>
      </div>
      <section className="card">
        <div className="card-hd">
          <div>
            <h4>저장된 제안</h4>
            <p>운송 시나리오 결과에서 저장한 항목입니다</p>
          </div>
        </div>
        <div className="card-bd grid savedgrid">
          {items.map((s) => (
            <div className="savedcard" key={s.id}>
              <div className="tp">
                <Badge tone={s.tag}>{s.tagLabel}</Badge>
                <span className="mono" style={{ marginLeft: "auto", fontSize: 11, color: "var(--faint)" }}>
                  {s.id}
                </span>
              </div>
              <h5>{s.title}</h5>
              <div className="kv">
                <span>
                  비용 <b>{s.cost}</b>
                </span>
                <span>
                  소요 <b>{s.days}</b>
                </span>
                <span>
                  등급 <b>{s.grade}</b>
                </span>
              </div>
              <div className="kv" style={{ marginTop: 4, fontSize: 11, color: "var(--faint)" }}>
                {s.when}
              </div>
              <div className="act">
                <button className="btn sm" style={{ flex: 1, justifyContent: "center" }} onClick={() => onOpen(s.id, s.tagLabel)}>
                  <i className="ti ti-external-link" />
                  열기
                </button>
                <button className="btn sm ghost" onClick={() => onUnbookmark(s.id)} title="보관함에서 빼기 (시나리오 자체는 안 지워짐)">
                  <i className="ti ti-bookmark-off" />
                </button>
              </div>
            </div>
          ))}
          <div className="savedempty">
            <div>
              <i className="ti ti-bookmark-plus" style={{ fontSize: 22 }} />
              <div style={{ marginTop: 6 }}>
                "제안서 저장" 버튼으로
                <br />
                등록된 시나리오 중에서 골라 담으세요
              </div>
            </div>
          </div>
        </div>
      </section>

      {pickerOpen && (
        <ProposalPicker unsaved={unsaved} onPick={onAddToBookmark} onClose={() => setPickerOpen(false)} />
      )}
    </section>
  );
}

function ProposalPicker({
  unsaved,
  onPick,
  onClose,
}: {
  unsaved: SavedScenario[];
  onPick: (scenarioId: string) => void;
  onClose: () => void;
}) {
  return (
    <>
      <div className="scrim open" onClick={onClose} />
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: "#fff",
          borderRadius: 16,
          padding: 0,
          width: "min(620px, 92vw)",
          maxHeight: "82vh",
          display: "flex",
          flexDirection: "column",
          zIndex: 90,
          boxShadow: "0 24px 70px rgba(9,24,44,.3)",
          overflow: "hidden",
        }}
      >
        <div className="card-hd" style={{ padding: "16px 20px" }}>
          <div>
            <h4>저장 안 된 시나리오</h4>
            <p>운송 시나리오에서 등록됐지만 아직 보관함엔 없는 것들입니다. 골라서 저장하세요.</p>
          </div>
          <div className="spacer" />
          <button className="btn sm ghost" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>
        <div style={{ overflowY: "auto", padding: "0 20px 20px", display: "flex", flexDirection: "column", gap: 8 }}>
          {unsaved.length === 0 && (
            <div className="coordwait" style={{ color: "var(--muted)", padding: "20px 0", textAlign: "center" }}>
              대기 중인 시나리오가 없습니다. 운송 시나리오에서 "이 경로 선택"으로 먼저 등록해보세요.
            </div>
          )}
          {unsaved.map((sc) => (
            <div
              key={sc.scenario_id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                border: "1px solid var(--line)",
                borderRadius: 10,
                padding: "10px 12px",
                flexWrap: "wrap",
              }}
            >
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>{sc.scenario_name}</div>
                <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>
                  {sc.route.origin_name} → {sc.route.destination_name} · ${Math.round(sc.metrics.shipment_cost_usd).toLocaleString()} ·{" "}
                  {sc.metrics.total_days}일
                </div>
              </div>
              <span className="mono" style={{ fontSize: 11, color: "var(--faint)" }}>
                {sc.scenario_id}
              </span>
              <button className="btn sm blue" onClick={() => onPick(sc.scenario_id)}>
                <i className="ti ti-bookmark-plus" />
                저장
              </button>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
