from __future__ import annotations

from app.dataset.loader import load_dataset

# The dataset has no live shipment-tracking feed. These 12 shipments are a
# fixed, hand-written demo set (not a generated/random dataset file) so the
# dashboard always has enough to show, per spec section 15.5's status mix
# (7 in transit / 2 delayed / 2 planned / 1 completed). Logged in TODO.md.
DEMO_SHIPMENTS = [
    {"shipment_id": "SHIP-001", "cargo": "완성차 200대", "origin": "Ulsan", "destination": "Munich", "progress_percent": 62, "eta": "2026-09-05", "current_mode": "sea", "risk_level": "MEDIUM", "cii_grade": "B", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-002", "cargo": "완성차 120대", "origin": "Busan", "destination": "Southampton", "progress_percent": 41, "eta": "2026-09-12", "current_mode": "sea", "risk_level": "LOW", "cii_grade": "A", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-003", "cargo": "자동차 부품 18톤", "origin": "Incheon", "destination": "Vienna", "progress_percent": 78, "eta": "2026-08-20", "current_mode": "air", "risk_level": "LOW", "cii_grade": "B", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-004", "cargo": "완성차 80대", "origin": "Ulsan", "destination": "Hamburg", "progress_percent": 55, "eta": "2026-09-08", "current_mode": "sea", "risk_level": "HIGH", "cii_grade": "C", "status": "DELAYED"},
    {"shipment_id": "SHIP-005", "cargo": "자동차 부품 22톤", "origin": "Busan", "destination": "Antwerp", "progress_percent": 33, "eta": "2026-09-15", "current_mode": "sea", "risk_level": "MEDIUM", "cii_grade": "B", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-006", "cargo": "완성차 150대", "origin": "Bremerhaven", "destination": "Munich", "progress_percent": 88, "eta": "2026-08-18", "current_mode": "truck", "risk_level": "LOW", "cii_grade": "A", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-007", "cargo": "일반화물 30톤", "origin": "Hamburg", "destination": "Duisburg", "progress_percent": 19, "eta": "2026-08-22", "current_mode": "truck", "risk_level": "HIGH", "cii_grade": "C", "status": "DELAYED"},
    {"shipment_id": "SHIP-008", "cargo": "완성차 60대", "origin": "Incheon", "destination": "Genoa", "progress_percent": 70, "eta": "2026-09-01", "current_mode": "sea", "risk_level": "LOW", "cii_grade": "B", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-009", "cargo": "자동차 부품 15톤", "origin": "Munich", "destination": "Frankfurt", "progress_percent": 5, "eta": "2026-08-14", "current_mode": "rail", "risk_level": "LOW", "cii_grade": "A", "status": "PLANNED"},
    {"shipment_id": "SHIP-010", "cargo": "완성차 100대", "origin": "Ulsan", "destination": "Bremerhaven", "progress_percent": 0, "eta": "2026-09-20", "current_mode": "sea", "risk_level": "MEDIUM", "cii_grade": "B", "status": "PLANNED"},
    {"shipment_id": "SHIP-011", "cargo": "완성차 200대", "origin": "Ulsan", "destination": "Bremerhaven", "progress_percent": 45, "eta": "2026-08-30", "current_mode": "sea", "risk_level": "MEDIUM", "cii_grade": "B", "status": "IN_TRANSIT"},
    {"shipment_id": "SHIP-012", "cargo": "일반화물 25톤", "origin": "Busan", "destination": "Valencia", "progress_percent": 100, "eta": "2026-08-05", "current_mode": "sea", "risk_level": "LOW", "cii_grade": "A", "status": "COMPLETED"},
]


def _severity(score: float) -> str:
    if score >= 75:
        return "CRITICAL"
    if score >= 50:
        return "HIGH"
    if score >= 25:
        return "MEDIUM"
    return "LOW"


def get_dashboard_summary() -> dict:
    dataset = load_dataset()

    resource_summary = {
        "available_sea_services": sum(len(c.services) for c in dataset.sea),
        "available_rail_services": sum(len(c.services) for c in dataset.rail),
        "available_air_services": sum(len(c.services) for c in dataset.air),
        "available_truck_services": sum(len(c.services) for c in dataset.road),
    }

    active_risks = []
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for port in dataset.ports:
        status = port["status"]
        score = port["risk"]["risk_score"] * 100
        if status.get("congestion_level") in ("HIGH", "CRITICAL") or status.get("strike_active"):
            severity = _severity(score if score >= 25 else 50)
            active_risks.append(
                {
                    "risk_id": f"RISK-PORT-{port['port_id']}",
                    "source_type": "PORT",
                    "source_id": port["port_id"],
                    "title": f"{port['port_name']} 혼잡도 {status.get('congestion_level', 'N/A')}",
                    "severity": severity,
                    "current_location": port["port_name"],
                    "expected_impact": f"예상 지연 {port['processing']['average_waiting_hours']:.0f}시간",
                    "expected_delay_hours": port["processing"]["average_waiting_hours"],
                }
            )
            risk_counts[severity.lower()] += 1

    for corridor in dataset.road_corridors:
        for incident in corridor.get("active_incidents", []):
            score = corridor["risk"]["risk_score"] * 100
            severity = _severity(score)
            active_risks.append(
                {
                    "risk_id": f"RISK-ROAD-{corridor['corridor_id']}",
                    "source_type": "ROAD",
                    "source_id": corridor["corridor_id"],
                    "title": f"{corridor['origin']['name']}-{corridor['destination']['name']} 구간 {incident['incident_type']}",
                    "severity": severity,
                    "current_location": corridor["origin"]["name"],
                    "expected_impact": f"예상 지연 {incident.get('expected_delay_hours', 0):.0f}시간",
                    "expected_delay_hours": incident.get("expected_delay_hours", 0),
                }
            )
            risk_counts[severity.lower()] += 1

    active_risks.sort(key=lambda r: r["expected_delay_hours"], reverse=True)

    return {
        "resource_summary": resource_summary,
        "risk_summary": risk_counts,
        "active_risks": active_risks[:8],
        "active_shipments": DEMO_SHIPMENTS,
    }
