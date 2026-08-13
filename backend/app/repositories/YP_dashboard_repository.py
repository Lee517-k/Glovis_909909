from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.yp_data_repository import DEFAULT_DB_PATH


class YPDashboardRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = db_path

    def summary(self) -> dict[str, object]:
        connection = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            modes = [dict(row) for row in connection.execute("""SELECT LOWER(mode) mode,COUNT(*) services,
                COUNT(DISTINCT carrier_id) carriers FROM carrier_capabilities
                WHERE is_active=1 AND validation_status!='excluded' GROUP BY LOWER(mode) ORDER BY services DESC""")]
            resources = dict(connection.execute("""SELECT COUNT(*) total_services,COUNT(DISTINCT carrier_id) total_carriers,
                SUM(CASE WHEN validation_status='verified' THEN 1 ELSE 0 END) verified_services
                FROM carrier_capabilities WHERE is_active=1 AND validation_status!='excluded'""").fetchone())
            resources["total_locations"] = connection.execute("""SELECT COUNT(*) FROM (SELECT origin_location_id location_id FROM carrier_capabilities WHERE is_active=1 UNION SELECT destination_location_id FROM carrier_capabilities WHERE is_active=1) WHERE location_id IS NOT NULL""").fetchone()[0]
            status_rows = connection.execute("SELECT UPPER(status) status,COUNT(*) count FROM scenarios GROUP BY UPPER(status)").fetchall()
            statuses = {row["status"]: row["count"] for row in status_rows}
            scenarios = [dict(row) for row in connection.execute("""SELECT scenario_id,scenario_name,status,origin_name,destination_name,
                cargo_type,quantity,quantity_unit,modes_json,cost_usd_per_vehicle,total_days,reliability,etd,eta,
                COALESCE((SELECT MAX(expected_delay_hours) FROM scenario_legs l WHERE l.scenario_id=s.scenario_id),0) delay_hours
                FROM scenarios s ORDER BY COALESCE(updated_at,created_at) DESC LIMIT 8""")]
            risks = [dict(row) for row in connection.execute("""SELECT s.scenario_id,s.origin_name,s.destination_name,
                MAX(COALESCE(l.expected_delay_hours,0)) delay_hours,MAX(COALESCE(l.delay_reason,'')) reason
                FROM scenarios s JOIN scenario_legs l ON l.scenario_id=s.scenario_id
                WHERE COALESCE(l.expected_delay_hours,0)>0 GROUP BY s.scenario_id ORDER BY delay_hours DESC LIMIT 6""")]
            insights = [dict(row) for row in connection.execute("""SELECT insight_id,severity,title,message,recommendation,source_name
                ,action_type,action_label FROM dashboard_ai_insights WHERE is_active=1 ORDER BY priority DESC,created_at DESC LIMIT 5""")]
            routes = [dict(row) for row in connection.execute("""SELECT DISTINCT origin_node_id,origin_name,destination_node_id,destination_name,LOWER(mode) mode
                FROM scenario_legs WHERE origin_node_id IS NOT NULL AND destination_node_id IS NOT NULL ORDER BY scenario_id DESC LIMIT 48""")]
        finally:
            connection.close()
        mode_counts = {row["mode"]: row["services"] for row in modes}
        active = [row for row in scenarios if str(row["status"]).upper() in {"ACTIVE", "IN_TRANSIT"}]
        if not active:
            active = scenarios[: min(5, len(scenarios))]
        shipments = [{"shipment_id": row["scenario_id"], "cargo": row["cargo_type"],
                      "origin": row["origin_name"], "destination": row["destination_name"],
                      "progress_percent": 65 if str(row["status"]).upper() in {"ACTIVE", "IN_TRANSIT"} else 100 if str(row["status"]).upper() in {"CLOSED", "COMPLETED"} else 15,
                      "eta": row["eta"], "current_mode": _first_mode(row["modes_json"]),
                      "cii_grade": "B", "status": row["status"]} for row in active]
        for insight in insights:
            insight["action_type"] = {"SCENARIO": "scenario", "TRACKING": "tracking", "NETWORK": "network"}.get(str(insight.get("action_type", "")).upper(), "dashboard")
        return {"resources": resources, "modes": modes,
                "shipments": {"total": sum(statuses.values()), "active": statuses.get("ACTIVE", 0) + statuses.get("IN_TRANSIT", 0), "completed": statuses.get("CLOSED", 0) + statuses.get("COMPLETED", 0), "planned": statuses.get("CONFIRMED", 0) + statuses.get("PLANNED", 0)},
                "scenarios": scenarios, "risks": risks, "insights": insights,
                "resource_summary": {"available_sea_services": mode_counts.get("sea", 0), "available_rail_services": mode_counts.get("rail", 0), "available_air_services": mode_counts.get("air", 0), "available_truck_services": mode_counts.get("road", mode_counts.get("truck", 0)), **resources},
                "risk_summary": {"critical": sum(r["delay_hours"] >= 72 for r in risks), "high": sum(24 <= r["delay_hours"] < 72 for r in risks), "medium": sum(0 < r["delay_hours"] < 24 for r in risks), "low": 0},
                "shipment_summary": {"total": sum(statuses.values()), "active": len(active), "completed": statuses.get("CLOSED", 0) + statuses.get("COMPLETED", 0), "planned": statuses.get("CONFIRMED", 0) + statuses.get("PLANNED", 0)},
                "network_routes": routes, "active_shipments": shipments, "ai_insights": insights}


def _first_mode(raw: str | None) -> str:
    import json
    try:
        modes = json.loads(raw or "[]")
        mode = str(modes[-1] if modes else "road").lower()
        return "truck" if mode == "road" else mode
    except (TypeError, ValueError):
        return "truck"
