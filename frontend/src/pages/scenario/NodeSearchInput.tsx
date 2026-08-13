import { useEffect, useId, useState } from "react";
import type { NegotiationNode } from "../../types/negotiation";

const NODE_TYPE_LABEL: Record<string, string> = {
  seaport: "해상",
  airport: "항공",
  rail_terminal: "철도",
  distribution_center: "내륙DC",
  vehicle_yard: "야드",
  plant: "공장",
  warehouse: "창고",
};

export function nodeOptionLabel(nd: { name: string; node_id: string; node_type?: string | null }): string {
  const typeLabel = nd.node_type ? (NODE_TYPE_LABEL[nd.node_type] ?? nd.node_type) : null;
  return typeLabel ? `${nd.name} · ${typeLabel} (${nd.node_id})` : `${nd.name} (${nd.node_id})`;
}

function extractCode(text: string): string | null {
  const m = text.match(/\(([^)]+)\)\s*$/);
  return m ? m[1] : null;
}

// 브라우저 기본 <datalist>로 타이핑 검색을 구현한다 — 커스텀 드롭다운 없이
// input에 입력하면 브라우저가 알아서 후보를 필터링해 보여준다.
export function NodeSearchInput({
  label,
  nodes,
  value,
  onChange,
  wide,
}: {
  label: string;
  nodes: NegotiationNode[];
  value: string;
  onChange: (nodeId: string) => void;
  wide?: boolean;
}) {
  const listId = useId();
  const [text, setText] = useState("");

  useEffect(() => {
    const nd = nodes.find((n) => n.node_id === value);
    setText(nd ? nodeOptionLabel(nd) : value);
    // nodes도 deps에 넣는다 — 마운트 시점엔 노드 목록이 아직 [](로딩 중)이라
    // value만 보고 있으면 나중에 목록이 실제로 도착해도 라벨이 안 바뀐다.
  }, [value, nodes]);

  function handleInput(raw: string) {
    setText(raw);
    const byLabel = nodes.find((n) => nodeOptionLabel(n) === raw);
    const code = extractCode(raw);
    const byCode = code ? nodes.find((n) => n.node_id === code) : undefined;
    const match = byLabel ?? byCode;
    if (match) onChange(match.node_id);
  }

  // 못 찾은 텍스트를 그대로 남겨두면, 빨간 경고가 떠 있는데도 실제 실행은
  // (한 번도 안 바뀐) 예전 값으로 조용히 되는 모순이 생긴다. 포커스를
  // 벗어나면 항상 지금 확정된 값의 라벨로 되돌려서 입력창이 거짓말하지
  // 않게 한다.
  function handleBlur() {
    const nd = nodes.find((n) => n.node_id === value);
    setText(nd ? nodeOptionLabel(nd) : value);
  }

  const resolved = nodes.find((n) => nodeOptionLabel(n) === text);

  return (
    <div className={`node${wide ? " wide" : ""}`} style={{ padding: 10 }}>
      <div className="nt" style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
        {label}
      </div>
      <input
        className="nv"
        list={listId}
        value={text}
        onChange={(e) => handleInput(e.target.value)}
        onBlur={handleBlur}
        placeholder="지명 검색 (예: 부산, 함부르크)"
        style={{ width: "100%", border: "1px solid var(--line)", borderRadius: 6, padding: "4px 6px" }}
      />
      <datalist id={listId}>
        {nodes.map((n) => (
          <option key={n.node_id} value={nodeOptionLabel(n)} />
        ))}
      </datalist>
      <div style={{ fontSize: 10.5, marginTop: 3, color: resolved || nodes.length === 0 ? "var(--muted)" : "var(--danger)" }}>
        {nodes.length === 0
          ? "노드 목록 불러오는 중..."
          : resolved
            ? `${resolved.node_id} · ${NODE_TYPE_LABEL[resolved.node_type ?? ""] ?? resolved.node_type ?? "-"}${resolved.country ? " · " + resolved.country : ""}`
            : "일치하는 노드를 찾지 못했습니다 — 목록에서 골라주세요"}
      </div>
    </div>
  );
}
