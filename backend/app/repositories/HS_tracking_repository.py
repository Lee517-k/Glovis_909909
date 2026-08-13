"""'운송 추적' 화면용 조회 로직.

DB 원본(scenarios / scenario_legs, senario_ver2/schema.sql 구조)을 읽어
프론트엔드가 그대로 렌더링할 수 있는 형태로 가공한다.

progress_percent/shipment_status는 저장하지 않고 ATD/ATA로 조회 시점에 역산한다
(schema.sql 설계 원칙). 계산 로직은 _compute_tracking()에 직접 구현했다
(senario_ver2/tracking.py는 참고만 하고 그대로 가져다 쓰지 않음).

담당 기능
  1. KPI 5종 집계          -> get_tracking_kpis()
  2. 화물 검색/필터/정렬    -> search_shipments()   ← 화면 상단 검색창
  3. 화물 상세(요약 카드)   -> get_shipment_detail()
  4. 구간 타임라인/여정     -> get_shipment_segments()
  5. 지도용 경로 지오메트리 -> get_shipment_route()
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from app.db.scenario_tracking_store import get_scenario_tracking_store
from app.domain.presentation import MODE_HEX, MODE_KO, TONE_DANGER, TONE_WARN, segment_icon
from app.planning.carbon import AVG_VEHICLE_WEIGHT_TON, grade_from_co2_per_ton

# DRAFT는 저장만 해둔 비교용 시나리오라 화물(추적 대상)이 아니다.
TRACKED_STATUSES = ("CONFIRMED", "ACTIVE", "CLOSED")

STATUS_LABEL_KO = {"PLANNED": "계획", "IN_TRANSIT": "운송중", "COMPLETED": "완료"}


# ---------------------------------------------------------------------------
# 추적 상태 역산 (ATD/ATA -> 진행률/상태/현재위치/지연/리스크)
# ---------------------------------------------------------------------------
def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _compute_tracking(scenario: dict, legs: list[dict], now: datetime) -> dict:
    """ATD/ATA로 진행률·상태·현재위치·지연·리스크를 역산한다. 저장 안 함."""
    leg_states: dict[int, str] = {}
    delay_total = 0.0

    for leg in legs:
        l_eta = _dt(leg["eta"])
        l_atd, l_ata = _dt(leg.get("atd")), _dt(leg.get("ata"))
        span_h = leg["transit_hours"] or 0.0

        if l_ata:
            status = "COMPLETED"
            delay_total += max(0.0, (l_ata - l_eta).total_seconds() / 3600)
        elif l_atd:
            status = "IN_TRANSIT"
            overdue = max(0.0, (now - l_eta).total_seconds() / 3600)
            delay_total += overdue or (leg.get("expected_delay_hours") or 0.0)
        else:
            status = "PLANNED"
            delay_total += leg.get("expected_delay_hours") or 0.0
        leg_states[leg["sequence"]] = status

    statuses = list(leg_states.values())
    if all(s == "COMPLETED" for s in statuses):
        shipment_status, progress = "COMPLETED", 100
    elif all(s == "PLANNED" for s in statuses):
        shipment_status, progress = "PLANNED", 0
    else:
        shipment_status = "IN_TRANSIT"
        # The DB records route milestones (leg ATD/ATA), not live GPS coordinates.
        # Treat every leg as one route step so a long sea leg does not force the
        # shipment to 97~99% before its inland handoff legs are completed.
        weights = [1.0 for _ in legs]
        completed_weight = sum(
            weight for leg, weight in zip(legs, weights)
            if leg_states[leg["sequence"]] == "COMPLETED"
        )
        active_weight = sum(
            weight * 0.5
            for leg, weight in zip(legs, weights)
            if leg_states[leg["sequence"]] == "IN_TRANSIT"
        )
        progress = min(99, max(1, round((completed_weight + active_weight) / (sum(weights) or 1.0) * 100)))

    risk = ("HIGH" if delay_total > 24 else "MEDIUM" if delay_total > 8
            else "LOW" if delay_total > 0 else "NONE")

    cur = next((l for l in legs if leg_states[l["sequence"]] == "IN_TRANSIT"), None)
    if cur:
        location = f"{cur.get('origin_name')} → {cur.get('destination_name')} 이동 중"
    elif shipment_status == "COMPLETED":
        location = f"{legs[-1].get('destination_name')} 도착 완료"
    elif shipment_status == "PLANNED":
        location = f"{legs[0].get('origin_name')} 출발 대기"
    else:
        done = [l for l in legs if leg_states[l["sequence"]] == "COMPLETED"]
        nxt = next((l for l in legs if leg_states[l["sequence"]] == "PLANNED"), None)
        here = done[-1]["destination_name"] if done else legs[0]["origin_name"]
        location = f"{here} 환적 대기 (다음: {nxt['destination_name']})" if nxt else f"{here} 대기"

    eta = _dt(scenario["eta"])
    eta_revised = eta + timedelta(hours=delay_total) if delay_total else eta
    return {
        "shipment_status": shipment_status,
        "progress_percent": progress,
        "current_location": location,
        "delay_hours": round(delay_total, 1),
        "risk_level": risk,
        "on_schedule": delay_total <= 0,
        "eta_revised": eta_revised.isoformat(timespec="minutes"),
        "leg_status_by_seq": leg_states,
        "leg_progress_by_seq": {
            leg["sequence"]: (
                1.0 if leg_states[leg["sequence"]] == "COMPLETED" else
                0.5
                if leg_states[leg["sequence"]] == "IN_TRANSIT" else 0.0
            ) for leg in legs
        },
    }


# ---------------------------------------------------------------------------
# 표기 헬퍼
# ---------------------------------------------------------------------------
def _shipment_row(scenario: dict, legs: list[dict], now: datetime) -> dict:
    """목록 카드 1건. 키 이름은 프론트 controlTowerApi.ShipmentRow 와 맞춘다."""
    tr = _compute_tracking(scenario, legs, now)
    modes = list(dict.fromkeys(l["mode"] for l in legs))
    co2 = scenario["co2_kg_per_vehicle"]
    grade = grade_from_co2_per_ton(co2, AVG_VEHICLE_WEIGHT_TON) if co2 is not None else None
    badge = _status_badge(tr)
    return {
        "id": scenario["scenario_id"],
        "lane": f"{scenario['origin_name']} → {scenario['destination_name']}",
        "from": scenario["origin_node_id"],
        "to": scenario["destination_node_id"],
        "cargo": f"{scenario.get('vehicle_type') or scenario['cargo_type']} {scenario['quantity']}대",
        "modes": modes,
        "mode_labels": [MODE_KO.get(m, m) for m in modes],
        "pct": tr["progress_percent"],
        "tone": (TONE_DANGER if badge[0] == "danger" else TONE_WARN if badge[0] == "warn"
                 else MODE_HEX.get(modes[-1] if modes else "", "#1668C4")),
        "loc": tr["current_location"],
        "eta": tr["eta_revised"],
        "eta_planned": scenario["eta"],
        "eta_forecast": tr["eta_revised"],
        "delay_days": round(tr["delay_hours"] / 24) if tr["delay_hours"] else 0,
        "st": badge,
        "status": tr["shipment_status"],
        "status_label": STATUS_LABEL_KO[tr["shipment_status"]],
        "g": grade,
        "cii": None,  # 이 스키마엔 선박 IMO 정보가 없어 CII 산출 불가
        "co2_kg": scenario["shipment_co2_kg"],
        "risk_score": None,
        "risk_level": tr["risk_level"],
        "carriers": list(dict.fromkeys(l["carrier_name"] for l in legs)),
        "region_id": None,  # 이 스키마엔 지역권 개념이 없음 (운송사 배분은 ct_regions 소관 유지)
        "open_alerts": 1 if tr["risk_level"] != "NONE" else 0,
    }


def _status_badge(tr: dict) -> list:
    """상태 배지 [tone, label]."""
    if tr["risk_level"] == "HIGH":
        return ["danger", "조치 필요"]
    if not tr["on_schedule"]:
        return ["warn", f"지연 {round(tr['delay_hours'])}h"]
    if tr["shipment_status"] == "COMPLETED":
        return ["ok", "완료"]
    if tr["shipment_status"] == "PLANNED":
        return ["gray", "계획"]
    return ["ok", "정상"]


def _rows_now(store, statuses: tuple[str, ...], now: datetime) -> list[dict]:
    scenarios = store.list_scenarios(statuses)
    legs_map = store.legs_for_many([s["scenario_id"] for s in scenarios])
    return [_shipment_row(s, legs_map.get(s["scenario_id"], []), now) for s in scenarios]


# ---------------------------------------------------------------------------
# 1. KPI
# ---------------------------------------------------------------------------
def get_tracking_kpis() -> dict:
    """운송 추적 상단 KPI 5종.

    진행중       = shipment_status가 IN_TRANSIT인 건수
    지연         = 진행중 중 on_schedule=False (역산된 지연) 인 건수
    리스크 감시  = 진행중 중 risk_level이 MEDIUM/HIGH 인 건수
    오늘 도착    = 진행중 중 eta_revised 날짜가 오늘인 건수
    환적 대기    = 진행중 중 현재위치가 '환적 대기'인 건수
    """
    now = datetime.now()
    store = get_scenario_tracking_store()
    rows = _rows_now(store, TRACKED_STATUSES, now)

    active = [r for r in rows if r["status"] == "IN_TRANSIT"]
    delayed = [r for r in active if r["st"][0] in ("warn", "danger")]
    watch = [r for r in active if r["risk_level"] in ("MEDIUM", "HIGH")]
    transship = [r for r in active if "환적 대기" in r["loc"]]
    today = date.today().isoformat()
    arriving_today = [r for r in active if r["eta"][:10] == today]
    on_time_pool = [r for r in rows if r["status"] != "PLANNED"]
    on_time_rate = (
        round(100 * sum(1 for r in on_time_pool if r["delay_days"] == 0) / len(on_time_pool), 1)
        if on_time_pool else 0.0
    )

    c = {
        "active_total": len(active), "delayed": len(delayed), "watch": len(watch),
        "arriving_today": len(arriving_today), "transship_wait": len(transship),
        "on_time_rate": on_time_rate,
    }
    cards = [
        {"icon": "ti-package", "label": "진행중", "value": c["active_total"], "unit": "건",
         "sub": "f전체 활성 화물", "tone": None},
        {"icon": "ti-alert-triangle", "label": "지연", "value": c["delayed"], "unit": "건",
         "sub": "d즉시 조치 필요", "tone": TONE_DANGER},
        {"icon": "ti-shield-exclamation", "label": "리스크 감시", "value": c["watch"], "unit": "건",
         "sub": "f통관·기상 사유", "tone": TONE_WARN},
        {"icon": "ti-plane-arrival", "label": "오늘 도착", "value": c["arriving_today"], "unit": "건",
         "sub": f"u정시 도착률 {c['on_time_rate']}%", "tone": None},
        {"icon": "ti-transfer", "label": "환적 대기", "value": c["transship_wait"], "unit": "건",
         "sub": "f환적항 대기중", "tone": None},
    ]
    return {**c, "in_transit": c["active_total"], "cards": cards}


# ---------------------------------------------------------------------------
# 2. 검색 / 필터 / 정렬
# ---------------------------------------------------------------------------
def search_shipments(
    q: str | None = None,
    status: str | None = None,
    mode: str | None = None,
    region_id: str | None = None,
    eta_from: str | None = None,
    eta_to: str | None = None,
    scope: str = "active",
    sort: str = "eta",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """화면 검색창/필터/정렬 버튼이 호출하는 목록 API의 본체.

    ScenarioTrackingStore가 자유검색/페이징을 지원하지 않아 파이썬에서 거른다.
    """
    now = datetime.now()
    store = get_scenario_tracking_store()
    rows = _rows_now(store, TRACKED_STATUSES, now)

    if scope == "active":
        rows = [r for r in rows if r["status"] == "IN_TRANSIT"]
    elif scope == "completed":
        rows = [r for r in rows if r["status"] == "COMPLETED"]
    elif scope == "planned":
        rows = [r for r in rows if r["status"] == "PLANNED"]
    # scope == "all" -> 그대로

    if q:
        ql = q.strip().lower()
        rows = [r for r in rows if ql in " ".join([
            r["id"], r["lane"], r["cargo"], r["loc"], *r["carriers"]
        ]).lower()]
    if status:
        marks = {s.strip().upper() for s in status.split(",") if s.strip()}
        today = date.today().isoformat()
        rows = [r for r in rows if (
            r["status"] in marks
            or ("DELAYED" in marks and r["st"][0] in ("warn", "danger"))
            or ("AT_RISK" in marks and r["risk_level"] in ("MEDIUM", "HIGH"))
            or ("ARRIVING_TODAY" in marks and r["eta"][:10] == today)
            or ("TRANSSHIP_WAIT" in marks and "환적 대기" in r["loc"])
        )]
    if mode:
        marks = {m.strip().lower() for m in mode.split(",") if m.strip()}
        rows = [r for r in rows if marks & set(r["modes"])]
    if eta_from:
        rows = [r for r in rows if r["eta"][:10] >= eta_from]
    if eta_to:
        rows = [r for r in rows if r["eta"][:10] <= eta_to]
    # region_id: 이 스키마엔 지역권이 없어 파라미터만 받고 무시(호환 유지용)

    keyfn = {
        "eta": lambda r: r["eta"], "-eta": lambda r: r["eta"],
        "progress": lambda r: r["pct"], "-progress": lambda r: r["pct"],
        "risk": lambda r: r["risk_level"], "-risk": lambda r: r["risk_level"],
        "id": lambda r: r["id"], "-id": lambda r: r["id"],
        "name": lambda r: r["lane"].lower(), "-name": lambda r: r["lane"].lower(),
    }.get(sort, lambda r: r["eta"])
    rows.sort(key=keyfn, reverse=sort.startswith("-"))

    total = len(rows)
    return {
        "total": total, "limit": limit, "offset": offset,
        "query": {"q": q, "status": status, "mode": mode, "region_id": region_id,
                  "eta_from": eta_from, "eta_to": eta_to,
                  "scope": scope, "sort": sort},
        "items": rows[offset:offset + limit],
    }


# ---------------------------------------------------------------------------
# 3. 상세 (우측 요약 카드 + AI 알림)
# ---------------------------------------------------------------------------
def get_shipment_detail(shipment_id: str) -> dict | None:
    now = datetime.now()
    store = get_scenario_tracking_store()
    scenario = store.get_scenario(shipment_id)
    if scenario is None:
        return None
    legs = store.get_legs(shipment_id)
    tr = _compute_tracking(scenario, legs, now)
    base = _shipment_row(scenario, legs, now)

    delay_reason = next((l.get("delay_reason") for l in legs if l.get("delay_reason")), None)
    alert = None
    if tr["risk_level"] != "NONE":
        alert = f"{tr['current_location']} — 예상 지연 {tr['delay_hours']:.1f}시간"
        if delay_reason:
            alert += f" ({delay_reason})"

    detail = dict(base)
    detail.update({
        "shipmentId": scenario["scenario_id"],
        "cargoLabel": f"{base['cargo']} · {base['lane']}",
        "riskLabel": tr["risk_level"],
        "riskTone": ("ok" if tr["risk_level"] in ("NONE", "LOW")
                     else ("warn" if tr["risk_level"] == "MEDIUM" else "danger")),
        "co2Label": f"{base['g'] or '—'}등급 · {base['co2_kg']:,.0f}kg" if base["co2_kg"] else "—",
        "location": tr["current_location"],
        "locationDetail": tr["current_location"],
        "carrierLabel": " · ".join(base["carriers"]),
        "alert": alert,
        "kv": [
            {"label": "리스크", "value": tr["risk_level"]},
            {"label": "탄소 등급", "value": base["g"] or "—"},
            {"label": "현재 위치", "value": tr["current_location"]},
            {"label": "ETA", "value": tr["eta_revised"]},
        ],
        "alerts": [],  # 알림 테이블이 없어짐 — 위 alert 하나로 대체 (resolve_alert 참고)
    })
    return detail


# ---------------------------------------------------------------------------
# 4. 구간 타임라인 / 여정
# ---------------------------------------------------------------------------
def get_shipment_segments(shipment_id: str) -> dict | None:
    """'구간 진행'(계획 대비 실적)과 지도 하단 Journey Timeline 을 한 번에 제공."""
    now = datetime.now()
    store = get_scenario_tracking_store()
    scenario = store.get_scenario(shipment_id)
    if scenario is None:
        return None
    legs = store.get_legs(shipment_id)
    tr = _compute_tracking(scenario, legs, now)

    steps = []
    actual_total = 0.0
    for l in legs:
        status = tr["leg_status_by_seq"][l["sequence"]]
        actual_days = None
        actual_label = ""
        if l.get("atd") and l.get("ata"):
            actual_days = (_dt(l["ata"]) - _dt(l["atd"])).total_seconds() / 86400
            actual_total += actual_days
            actual_label = f"실제 {actual_days:.1f}일"
        elif status == "IN_TRANSIT":
            actual_label = "진행중"

        steps.append({
            "sequence": l["sequence"],
            "t": f"{l.get('origin_name')} → {l.get('destination_name')}",
            "s": f"{MODE_KO.get(l['mode'], l['mode'])} · {l['carrier_name']}",
            "p": f"계획 {(l['transit_hours'] or 0) / 24:.1f}일",
            "a": actual_label,
            "state": "done" if status == "COMPLETED" else "active" if status == "IN_TRANSIT" else "pending",
            "kind": "MOVE",
            "mode": l["mode"],
            "mode_label": MODE_KO.get(l["mode"], l["mode"]),
            "icon": segment_icon(None, l["mode"]),
            "carrier_id": l["carrier_id"],
            "carrier": l["carrier_name"],
            "on_time_pct": None,
            "grade": None,
            "grade_kind": None,
            "from": {"node_id": l["origin_node_id"], "name": l.get("origin_name")},
            "to": {"node_id": l["destination_node_id"], "name": l.get("destination_name")},
            "distance_km": l.get("distance_km"),
            "planned_days": round((l.get("transit_hours") or 0) / 24, 2),
            "actual_days": round(actual_days, 2) if actual_days is not None else None,
            "short": l.get("destination_name"),
        })

    planned_total = (scenario["total_transit_hours"] or 0) / 24
    return {
        "shipment_id": shipment_id,
        "steps": steps,
        "planned_days_total": round(planned_total, 2),
        "actual_days_total": round(actual_total, 2),
        "variance_days": round(actual_total - sum(
            s["planned_days"] for s in steps if s["actual_days"] is not None), 2),
    }


# ---------------------------------------------------------------------------
# 5. 지도용 경로
# ---------------------------------------------------------------------------
def get_shipment_route(shipment_id: str) -> dict | None:
    """지도 SVG가 쓰는 경로. 이 스키마엔 노드 좌표가 없어 node_id/상태만 반환한다.
    프론트는 worldmap.ts의 NodeKey 기반 arc()/hubDot()으로 node_id를 직접 그린다."""
    now = datetime.now()
    store = get_scenario_tracking_store()
    scenario = store.get_scenario(shipment_id)
    if scenario is None:
        return None
    legs = store.get_legs(shipment_id)
    tr = _compute_tracking(scenario, legs, now)

    out_legs = [{
        "from": {"node_id": l["origin_node_id"], "name": l.get("origin_name")},
        "to": {"node_id": l["destination_node_id"], "name": l.get("destination_name")},
        "mode": l["mode"],
        "color": MODE_HEX.get(l["mode"], "#5FA8FF"),
        "state": ("done" if tr["leg_status_by_seq"][l["sequence"]] == "COMPLETED" else
                  "active" if tr["leg_status_by_seq"][l["sequence"]] == "IN_TRANSIT" else "pending"),
        "progress_ratio": tr["leg_progress_by_seq"][l["sequence"]],
        "distance_km": l.get("distance_km"),
    } for l in legs]
    return {"shipment_id": shipment_id, "legs": out_legs, "nodes": [], "current": None, "bbox": None}


def resolve_alert(alert_id: int) -> bool:
    """AI 알림 '조치 완료' 처리 — 알림 테이블이 없어져서 지금은 항상 실패를 반환한다.
    TODO: 팀과 상의해 재설계 (예: leg의 delay_reason을 '확인함' 처리하는 방식 등)."""
    return False
