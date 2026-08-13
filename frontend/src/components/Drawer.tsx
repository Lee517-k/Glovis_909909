export interface DrawerStep {
  title: string;
  detail: string[];
  icon: string;
  tone?: "ok" | "warn";
}

export interface DrawerContent {
  title: string;
  icon: string;
  meta: string;
  steps: DrawerStep[];
}

export function Drawer({ content, onClose }: { content: DrawerContent | null; onClose: () => void }) {
  const open = content !== null;
  return (
    <>
      <div className={`scrim ${open ? "open" : ""}`} onClick={onClose} />
      <aside className={`drawer ${open ? "open" : ""}`}>
        {content && (
          <>
            <div className="dh">
              <h4>
                <i className={`ti ${content.icon}`} />
                <span>{content.title}</span>
              </h4>
              <div className="meta">{content.meta}</div>
            </div>
            <div className="db">
              <div className="tl">
                {content.steps.map((s, i) => (
                  <div className={`tlitem ${s.tone ?? ""}`} key={i}>
                    <div className="box">
                      <h6>
                        <i className={`ti ${s.icon}`} />
                        Step {i + 1} · {s.title}
                      </h6>
                      {s.detail.map((line, j) => (
                        <p key={j}>{line}</p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
        <div className="df">
          <button className="btn primary" style={{ flex: 1, justifyContent: "center" }}>
            <i className="ti ti-download" />
            전체 로그 내보내기
          </button>
          <button className="btn" onClick={onClose}>
            닫기
          </button>
        </div>
      </aside>
    </>
  );
}
