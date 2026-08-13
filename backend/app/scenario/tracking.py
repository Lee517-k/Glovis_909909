"""추적 상태 역산.

시나리오에는 ATD/ATA만 저장돼 있다. 진행률/상태/지연은 조회 시점(now)에
계산한다. 이렇게 하면 시간이 지나도 저장된 값이 안 틀어진다.

Ported as-is from the reference project's backend/glovis_scenario/tracking.py
— required by store.py (ScenarioStore.get/list call enrich()), even though
this feature's public API contract doesn't expose the "tracking" block.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _dt(s):
    return datetime.fromisoformat(s) if s else None


def _add_h(dt, hours):
    return dt + timedelta(hours=hours)


def compute(sc, now=None, assume_on_schedule=True):
    now = now or datetime.now()
    legs = sc["legs"]

    etd = _dt(sc["schedule"]["etd"])
    eta = _dt(sc["schedule"]["eta"])

    leg_states = []
    delay_total = 0.0
    elapsed_h = 0.0

    for l in legs:
        l_etd, l_eta = _dt(l["etd"]), _dt(l["eta"])
        l_atd, l_ata = _dt(l["atd"]), _dt(l["ata"])
        span_h = l["transit_hours"] or 0.0

        if assume_on_schedule:
            if not l_atd and l_etd and l_etd <= now:
                l_atd = l_etd
            if not l_ata and l_eta and l_eta <= now:
                l_ata = l_eta

        if l_ata:
            status = "COMPLETED"
            delay = round((l_ata - l_eta).total_seconds() / 3600, 1)
            delay_total += max(0.0, delay)
            elapsed_h += span_h
        elif l_atd:
            status = "IN_TRANSIT"
            run_h = (now - l_atd).total_seconds() / 3600
            elapsed_h += min(run_h, span_h)
            overdue = max(0.0, (now - l_eta).total_seconds() / 3600) if l_eta else 0.0
            delay = round(overdue or (l.get("expected_delay_hours") or 0.0), 1)
            delay_total += delay
        else:
            status = "PLANNED"
            delay = round(l.get("expected_delay_hours") or 0.0, 1)
            delay_total += delay

        leg_states.append({
            "sequence": l["sequence"],
            "leg_status": status,
            "delay_hours": delay,
            "eta_revised": (l_eta and delay
                            and _add_h(l_eta, delay).isoformat(timespec="minutes")) or None,
        })

    total_h = sc["schedule"]["total_transit_hours"] or 1.0

    if all(s["leg_status"] == "COMPLETED" for s in leg_states):
        status = "COMPLETED"
        progress = 100
    elif all(s["leg_status"] == "PLANNED" for s in leg_states):
        status = "PLANNED"
        progress = 0
    else:
        status = "IN_TRANSIT"
        progress = min(99, max(1, round(elapsed_h / total_h * 100)))

    if delay_total > 24:
        risk = "HIGH"
    elif delay_total > 8:
        risk = "MEDIUM"
    elif delay_total > 0:
        risk = "LOW"
    else:
        risk = "NONE"

    atd = next((l["atd"] for l in legs if l["atd"]), None)
    ata = legs[-1]["ata"] if status == "COMPLETED" else None
    eta_revised = _add_h(eta, delay_total) if (delay_total and eta) else eta

    cur = next((l for l, s in zip(legs, leg_states)
                if s["leg_status"] == "IN_TRANSIT"), None)
    if cur:
        location = f"{cur.get('origin_name')} → {cur.get('destination_name')} 이동 중"
        current_leg = cur["sequence"]
    elif status == "COMPLETED":
        location = f"{legs[-1].get('destination_name')} 도착 완료"
        current_leg = None
    elif status == "PLANNED":
        location = f"{legs[0].get('origin_name')} 출발 대기"
        current_leg = None
    else:
        done = [l for l, s in zip(legs, leg_states) if s["leg_status"] == "COMPLETED"]
        nxt = next((l for l, s in zip(legs, leg_states)
                    if s["leg_status"] == "PLANNED"), None)
        here = done[-1]["destination_name"] if done else legs[0].get("origin_name")
        location = (f"{here} 환적 대기 (다음: {nxt['destination_name']})"
                    if nxt else f"{here} 대기")
        current_leg = nxt["sequence"] if nxt else None

    return {
        "shipment_status": status,
        "progress_percent": progress,
        "current_leg": current_leg,
        "current_location": location,
        "elapsed_hours": round(elapsed_h, 1),
        "remaining_hours": round(max(0.0, total_h - elapsed_h), 1),
        "delay_hours": round(delay_total, 1),
        "risk_level": risk,
        "atd": atd,
        "ata": ata,
        "eta": eta.isoformat(timespec="minutes") if eta else None,
        "eta_revised": eta_revised.isoformat(timespec="minutes") if eta_revised else None,
        "on_schedule": delay_total <= 0,
        "legs": leg_states,
        "computed_at": now.isoformat(timespec="minutes"),
    }


def enrich(sc, now=None):
    """시나리오에 계산된 상태를 합쳐 반환한다."""
    st = compute(sc, now)
    out = {k: v for k, v in sc.items() if k != "legs"}
    out["tracking"] = {k: v for k, v in st.items() if k != "legs"}
    out["legs"] = [
        {**l, **{k: v for k, v in s.items() if k != "sequence"}}
        for l, s in zip(sc["legs"], st["legs"])
    ]
    return out
