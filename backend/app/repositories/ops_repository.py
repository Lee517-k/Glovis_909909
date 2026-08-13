"""나머지 화면(대시보드 알림 / 제안서 보관함 / 데이터 업로드 / 통합 검색) 로직."""

from __future__ import annotations

import csv
import io
import json
import statistics
import uuid
from datetime import datetime, timezone

from app.dataset.control_tower_seed import COLUMN_DICTIONARY, UPLOAD_IMPACT
from app.db.control_tower_store import get_control_tower_store
from app.domain.presentation import MODE_KO


# ---------------------------------------------------------------------------
# 대시보드 알림 패널
# ---------------------------------------------------------------------------
def _ago(iso: str | None) -> str:
    """'10분 전' / '3시간 전' 같은 상대 시각 문자열."""
    if not iso:
        return ""
    try:
        created = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - created).total_seconds()
    if delta < 3600:
        return f"{max(1, int(delta // 60))}분 전"
    if delta < 86400:
        return f"{int(delta // 3600)}시간 전"
    return f"{int(delta // 86400)}일 전"


def get_ops_alerts() -> dict:
    rows = get_control_tower_store().list_ops_alerts()
    items = [
        {
            "alert_id": r["alert_id"],
            "t": r["level"],           # critical | warning | info (프론트 클래스명)
            "lb": r["label"],
            "h": r["title"],
            "d": r["body"],
            "a": r["action_label"],
            "page": r["action_page"],
            "ago": _ago(r["created_at"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]
    counts = {"critical": 0, "warning": 0, "info": 0}
    for i in items:
        counts[i["t"]] = counts.get(i["t"], 0) + 1
    return {"alerts": items, "counts": counts, "total": len(items)}


def dismiss_ops_alert(alert_id: str) -> bool:
    return get_control_tower_store().dismiss_ops_alert(alert_id)


# ---------------------------------------------------------------------------
# 제안서 보관함
# ---------------------------------------------------------------------------
def list_saved_proposals() -> dict:
    rows = get_control_tower_store().list_saved_proposals()
    items = []
    for r in rows:
        modes = json.loads(r["modes_json"] or "[]")
        items.append({
            "id": r["proposal_id"],
            "t": r["title"],
            "cost": f"{r['cost_amount']:,.0f}원" if r["currency"] == "KRW" else f"{r['cost_amount']:,.0f} {r['currency']}",
            "days": f"{r['days']:g}일" if r["days"] is not None else "—",
            "esg": r["esg_grade"],
            "when": _ago(r["created_at"]),
            "tag": [r["tag_tone"], r["tag_label"]],
            "modes": modes,
            "mode_labels": [MODE_KO.get(m, m) for m in modes],
            "created_at": r["created_at"],
        })
    return {"total": len(items), "items": items}


def save_proposal(payload: dict) -> dict:
    store = get_control_tower_store()
    if not payload.get("proposal_id"):
        payload["proposal_id"] = f"SCEN-{uuid.uuid4().hex[:4].upper()}"
    store.save_proposal(payload)
    return {"proposal_id": payload["proposal_id"], "saved": True}


def delete_proposal(proposal_id: str) -> bool:
    return get_control_tower_store().delete_proposal(proposal_id)


# ---------------------------------------------------------------------------
# 데이터 업로드 — 컬럼 자동 매핑 + 이상치 검증
# ---------------------------------------------------------------------------
_DICT = {row[0].upper().replace(" ", ""): row for row in COLUMN_DICTIONARY}

# 운임으로 취급할 컬럼 후보(이상치 검사 대상)
_RATE_HINTS = ("OFR", "RATE", "FREIGHT", "운임")


def _decode(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _map_column(header: str) -> tuple[str, str, str, str]:
    """헤더 1개를 내부 필드로 매핑. 사전에 없으면 건너뜀 처리."""
    key = header.upper().replace(" ", "")
    if key in _DICT:
        _, field, note, tone, label = _DICT[key]
        return field, note, tone, label
    # 부분 일치도 한 번 시도한다(예: OFR_20DC_USD → OFR_20DC)
    for dict_key, row in _DICT.items():
        if dict_key and (dict_key in key or key in dict_key):
            return row[1], row[2], "warn", "확인 필요"
    return "—", "사전에 없는 컬럼", "gray", "건너뜀"


def analyze_upload(filename: str, raw: bytes) -> dict:
    """업로드된 운임표(CSV)를 읽어 컬럼 매핑안과 검증 이슈를 만든다.

    검증 항목
      1) 노드 사전에 없는 출발지/도착지 값
      2) 운임 컬럼의 이상치(중앙값 대비 +30% 초과)
      3) 선박명은 있는데 IMO 번호가 없는 행 (CII 등급 조회 불가)
    """
    text = _decode(raw)
    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    rows = list(reader)

    mapping = []
    for h in headers:
        field, note, tone, label = _map_column(h)
        mapping.append({"source": h, "target": field, "note": note, "tone": tone, "status": label})

    store = get_control_tower_store()
    known = set()
    for n in store.list_nodes():
        known.update({n["node_id"].upper(), (n["name_ko"] or "").upper(), (n["name_en"] or "").upper()})

    issues = []

    # 1) 노드 사전 미등록 값
    node_cols = [h for h in headers if h.upper().replace(" ", "") in ("POL", "POD", "FROM_NODE", "TO_NODE")]
    unknown: dict[str, list[int]] = {}
    for idx, row in enumerate(rows, start=2):  # 헤더가 1행
        for col in node_cols:
            val = (row.get(col) or "").strip()
            if val and val.upper() not in known:
                unknown.setdefault(val, []).append(idx)
    for val, lines in list(unknown.items())[:5]:
        suggestion = _suggest_node(store, val)
        issues.append({
            "t": "danger",
            "i": "ti-circle-x",
            "h": "행 " + ", ".join(map(str, lines[:3])) + (" …" if len(lines) > 3 else ""),
            "d": f'"{val}"이 노드 사전에 없습니다',
            "s": f"제안: {suggestion}" if suggestion else "노드 사전 등록이 필요합니다",
            "a": "일괄 적용",
            "rows": lines,
        })

    # 2) 운임 이상치
    for h in headers:
        if not any(hint in h.upper() for hint in _RATE_HINTS):
            continue
        values, line_no = [], []
        for idx, row in enumerate(rows, start=2):
            try:
                values.append(float(str(row.get(h, "")).replace(",", "")))
                line_no.append(idx)
            except (TypeError, ValueError):
                continue
        if len(values) < 3:
            continue
        median = statistics.median(values)
        outliers = [line_no[i] for i, v in enumerate(values) if median and v > median * 1.3]
        if outliers:
            issues.append({
                "t": "warn",
                "i": "ti-alert-triangle",
                "h": f"행 {outliers[0]}–{outliers[-1]}",
                "d": f"{h} 값이 중앙값 대비 +30%를 넘는 행이 {len(outliers)}건입니다",
                "s": "BAF 포함 여부를 확인해주세요",
                "a": "확인",
                "rows": outliers,
            })

    # 3) 선박명은 있는데 IMO 없음
    vessel_col = next((h for h in headers if h.upper().startswith("VESSEL")), None)
    imo_col = next((h for h in headers if "IMO" in h.upper()), None)
    if vessel_col:
        if imo_col is None:
            # IMO 컬럼 자체가 없으면 등장한 모든 선박이 조회 불가
            names = {(r.get(vessel_col) or "").strip() for r in rows}
        else:
            names = {(r.get(vessel_col) or "").strip() for r in rows
                     if not (r.get(imo_col) or "").strip()}
        missing = len(names - {""})
        if missing > 0:
            issues.append({
                "t": "warn",
                "i": "ti-alert-triangle",
                "h": f"선박 {missing}척",
                "d": "IMO 번호 미기재로 CII 등급을 조회할 수 없습니다",
                "s": "미기재 시 해당 구간은 ESG 등급만 산정됩니다",
                "a": "입력",
                "rows": [],
            })

    impact = [{"scenario_id": a, "current": b, "after": c, "tone": d, "delta": e}
              for (a, b, c, d, e) in UPLOAD_IMPACT]

    batch = {
        "batch_id": f"UPL-{uuid.uuid4().hex[:8].upper()}",
        "filename": filename,
        "row_count": len(rows),
        "column_count": len(headers),
        "status": "MAPPED",
        "mapping": mapping,
        "issues": issues,
        "impact": impact,
    }
    store.create_upload_batch(batch)
    batch["auto_mapped"] = sum(1 for m in mapping if m["tone"] == "ok")
    batch["needs_review"] = sum(1 for m in mapping if m["tone"] == "warn")
    batch["skipped"] = sum(1 for m in mapping if m["tone"] == "gray")
    return batch


def _suggest_node(store, value: str) -> str | None:
    """미등록 값과 가장 비슷한 노드를 제안한다(접두/부분 일치 기준)."""
    v = value.strip().upper()
    for n in store.list_nodes():
        for cand in (n["name_en"], n["name_ko"]):
            if cand and (cand.upper().startswith(v[:4]) or v.startswith(cand.upper()[:4])):
                return f"{n['node_id']}({n['name_ko']})"
    return None


def get_upload_batch(batch_id: str) -> dict | None:
    row = get_control_tower_store().get_upload_batch(batch_id)
    if row is None:
        return None
    return {
        "batch_id": row["batch_id"],
        "filename": row["filename"],
        "row_count": row["row_count"],
        "column_count": row["column_count"],
        "status": row["status"],
        "mapping": json.loads(row["mapping_json"] or "[]"),
        "issues": json.loads(row["issues_json"] or "[]"),
        "impact": json.loads(row["impact_json"] or "[]"),
        "created_at": row["created_at"],
        "committed_at": row["committed_at"],
    }


def commit_upload_batch(batch_id: str) -> dict | None:
    """3단계 '검증 · 반영'. 치명(danger) 이슈가 남아 있으면 반영을 막는다."""
    batch = get_upload_batch(batch_id)
    if batch is None:
        return None
    blocking = [i for i in batch["issues"] if i["t"] == "danger"]
    if blocking:
        return {"committed": False, "blocking_issues": len(blocking),
                "message": "치명 이슈를 먼저 해소해야 반영할 수 있습니다."}
    get_control_tower_store().commit_upload_batch(batch_id)
    return {"committed": True, "batch_id": batch_id, "impact": batch["impact"]}


# ---------------------------------------------------------------------------
# 통합 검색 (상단바)
# ---------------------------------------------------------------------------
def global_search(q: str, limit: int = 8) -> dict:
    """운송번호·항만·운송사·저장된 제안서를 한 번에 찾아 페이지 이동 정보까지 준다."""
    if not q or not q.strip():
        return {"q": q, "total": 0, "groups": []}

    raw = get_control_tower_store().global_search(q, limit)
    groups = [
        {"key": "shipments", "label": "화물", "page": "tracking",
         "items": [{"id": s["shipment_id"],
                    "title": s["shipment_id"],
                    "sub": f"{s['origin_name']} → {s['dest_name']} · {s['cargo_name']}",
                    "meta": s["status"]} for s in raw["shipments"]]},
        {"key": "nodes", "label": "거점", "page": "network",
         "items": [{"id": n["node_id"], "title": f"{n['name_ko']} ({n['node_id']})",
                    "sub": n["name_en"], "meta": n["node_type"]} for n in raw["nodes"]]},
        {"key": "carriers", "label": "운송사", "page": "network",
         "items": [{"id": c["carrier_id"], "title": c["carrier_name"],
                    "sub": c["description"], "meta": c["modes"]} for c in raw["carriers"]]},
        {"key": "proposals", "label": "제안서", "page": "saved",
         "items": [{"id": p["proposal_id"], "title": p["proposal_id"],
                    "sub": p["title"], "meta": ""} for p in raw["proposals"]]},
    ]
    groups = [g for g in groups if g["items"]]
    return {"q": q, "total": sum(len(g["items"]) for g in groups), "groups": groups}
