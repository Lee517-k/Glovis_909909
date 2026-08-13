from __future__ import annotations

import sqlite3
from pathlib import Path

from app.repositories.yp_data_repository import DEFAULT_DB_PATH
from app.repositories import HS_tracking_repository as tracking_repository


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
            routes = [dict(row) for row in connection.execute("""SELECT DISTINCT
                COALESCE(origin_node_id,origin_location_id) origin_node_id,origin_name,
                COALESCE(destination_node_id,destination_location_id) destination_node_id,destination_name,
                LOWER(mode) mode,NULL shipment_id
                FROM carrier_capabilities
                WHERE is_active=1 AND mapping_status='approved' AND validation_status!='excluded'
                  AND COALESCE(origin_node_id,origin_location_id) IS NOT NULL
                  AND COALESCE(destination_node_id,destination_location_id) IS NOT NULL
                UNION ALL
                SELECT origin_node_id,origin_name,destination_node_id,destination_name,LOWER(mode),scenario_id shipment_id
                FROM scenario_legs
                WHERE origin_node_id IS NOT NULL AND destination_node_id IS NOT NULL
                ORDER BY mode,origin_node_id,destination_node_id""")]
        finally:
            connection.close()
        mode_counts = {row["mode"]: row["services"] for row in modes}
        all_rows = tracking_repository.search_shipments(scope="all", sort="eta", limit=200)["items"]
        active = [row for row in all_rows if row["status"] == "IN_TRANSIT"]
        shipments = [{"shipment_id": row["id"], "cargo": row["cargo"],
                      "origin": row["lane"].split(" → ", 1)[0], "destination": row["lane"].split(" → ", 1)[-1],
                      "progress_percent": row["pct"], "eta": row["eta"],
                      "current_mode": row["modes"][-1] if row["modes"] else "truck",
                      "cii_grade": row["g"] or "-", "status": row["status"]} for row in active[:8]]
        severities = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for row in active:
            severity = "critical" if row["delay_days"] >= 3 else "high" if row["risk_level"] == "HIGH" or row["delay_days"] >= 1 else "medium" if row["risk_level"] == "MEDIUM" else "low"
            severities[severity] += 1
        for insight in insights:
            insight["action_type"] = {"SCENARIO": "scenario", "TRACKING": "tracking", "NETWORK": "network"}.get(str(insight.get("action_type", "")).upper(), "dashboard")
        return {"resources": resources, "modes": modes,
                "shipments": {"total": len(all_rows), "active": len(active), "completed": sum(row["status"] == "COMPLETED" for row in all_rows), "planned": sum(row["status"] == "PLANNED" for row in all_rows)},
                "scenarios": scenarios, "risks": risks, "insights": insights,
                "resource_summary": {"available_sea_services": mode_counts.get("sea", 0), "available_rail_services": mode_counts.get("rail", 0), "available_air_services": mode_counts.get("air", 0), "available_truck_services": mode_counts.get("road", mode_counts.get("truck", 0)), **resources},
                "risk_summary": severities,
                "shipment_summary": {"total": len(all_rows), "active": len(active), "completed": sum(row["status"] == "COMPLETED" for row in all_rows), "planned": sum(row["status"] == "PLANNED" for row in all_rows)},
                "network_routes": routes, "active_shipments": shipments, "ai_insights": insights}
