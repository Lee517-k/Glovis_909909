"""JSON <-> SQLite 저장/조회 모듈.

Ported from the reference project's backend/glovis_scenario/store.py, pointed
at this project's Data/glovis_merged.db (which already has matching
`scenarios` / `scenario_legs` tables).

    from app.scenario.store import ScenarioStore
    store = ScenarioStore(str(settings.merged_db_path))
    store.init()                    # creates tables only if missing
    store.save(scenario_dict)
    store.list(favorite_only=True)
    store.get("SCN-000001")
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.scenario.tracking import enrich

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class ScenarioStore:
    def __init__(self, path: str = "scenarios.db"):
        self.path = path

    def _con(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    # -- 초기화 --------------------------------------------------------
    def init(self, schema_path=None) -> bool:
        """테이블 생성. 이미 있으면 건너뛴다."""
        with self._con() as con:
            exists = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scenarios'"
            ).fetchone()
            if exists:
                return False
            con.executescript(open(schema_path or SCHEMA_PATH, encoding="utf-8").read())
        return True

    # -- 저장 -----------------------------------------------------------
    def save(self, sc: dict) -> str:
        """시나리오 1건 저장. 이미 있으면 덮어쓴다."""
        c, r, m = sc["cargo"], sc["route"], sc["metrics"]
        s = sc["schedule"]
        t = sc.get("trade", {})
        row = {
            "scenario_id": sc["scenario_id"],
            "scenario_name": sc["scenario_name"],
            "status": sc.get("status", "DRAFT"),
            "is_favorite": int(sc.get("is_favorite", False)),
            "cancelled_at": sc.get("cancelled_at"),
            "cancel_reason": sc.get("cancel_reason"),
            "closed_at": sc.get("closed_at"),
            "updated_at": sc.get("updated_at"),
            "created_at": sc.get("created_at") or datetime.now().isoformat(timespec="minutes"),
            "selected_axis": sc.get("selected_axis"),
            "cargo_type": c["cargo_type"],
            "vehicle_type": c.get("vehicle_type"),
            "quantity": c["quantity"],
            "quantity_unit": c.get("quantity_unit", "vehicle"),
            "origin_node_id": r["origin_node_id"],
            "origin_location_id": r["origin_location_id"],
            "origin_name": r.get("origin_name"),
            "destination_node_id": r["destination_node_id"],
            "destination_location_id": r["destination_location_id"],
            "destination_name": r.get("destination_name"),
            "path_json": json.dumps(r["path"], ensure_ascii=False),
            "modes_json": json.dumps(r["modes"], ensure_ascii=False),
            "leg_count": r.get("leg_count", len(sc["legs"])),
            "cost_usd_per_vehicle": m["cost_usd_per_vehicle"],
            "shipment_cost_usd": m["shipment_cost_usd"],
            "total_days": m["total_days"],
            "co2_kg_per_vehicle": m["co2_kg_per_vehicle"],
            "shipment_co2_kg": m["shipment_co2_kg"],
            "reliability": m["reliability"],
            "transfers": m.get("transfers"),
            "customs_days": m.get("customs_days"),
            "etd": s["etd"], "eta": s["eta"],
            "total_transit_hours": s["total_transit_hours"],
            "incoterm": t.get("incoterm"),
            "origin_country": t.get("origin_country"),
            "destination_country": t.get("destination_country"),
            "customs_required": int(bool(t.get("customs_required"))),
            "scenario_json": json.dumps(sc, ensure_ascii=False),
        }
        with self._con() as con:
            cols = [x[1] for x in con.execute("PRAGMA table_info(scenarios)")]
            vals = [row.get(k) for k in cols]
            con.execute(
                f"INSERT OR REPLACE INTO scenarios ({','.join(cols)}) "
                f"VALUES ({','.join('?' * len(cols))})", vals)
            con.execute("DELETE FROM scenario_legs WHERE scenario_id=?",
                        (sc["scenario_id"],))
            for l in sc["legs"]:
                con.execute("""INSERT INTO scenario_legs
                    (scenario_id,sequence,mode,carrier_id,carrier_name,service_id,
                     service_tier,source_dataset,origin_node_id,origin_location_id,
                     origin_name,destination_node_id,destination_location_id,
                     destination_name,distance_km,cost_usd_per_vehicle,transit_hours,
                     co2_kg_per_vehicle,reliability,etd,eta,atd,ata,
                     expected_delay_hours,delay_reason)
                    VALUES (""" + ",".join("?" * 25) + ")",
                    (sc["scenario_id"], l["sequence"], l["mode"], l["carrier_id"],
                     l["carrier_name"], l["service_id"], l.get("service_tier"),
                     l.get("source_dataset"), l["origin_node_id"],
                     l.get("origin_location_id"), l.get("origin_name"),
                     l["destination_node_id"], l.get("destination_location_id"),
                     l.get("destination_name"), l.get("distance_km"),
                     l.get("cost_usd_per_vehicle"), l.get("transit_hours"),
                     l.get("co2_kg_per_vehicle"), l.get("reliability"),
                     l["etd"], l["eta"], l.get("atd"), l.get("ata"),
                     l.get("expected_delay_hours"), l.get("delay_reason")))
        return sc["scenario_id"]

    def next_id(self) -> str:
        """SCN-000001 형식으로 다음 ID 발급"""
        with self._con() as con:
            row = con.execute(
                "SELECT scenario_id FROM scenarios "
                "WHERE scenario_id LIKE 'SCN-%' ORDER BY scenario_id DESC LIMIT 1"
            ).fetchone()
        n = int(row[0].split("-")[1]) + 1 if row else 1
        return f"SCN-{n:06d}"

    def exists(self, sid: str) -> bool:
        with self._con() as con:
            return con.execute("SELECT 1 FROM scenarios WHERE scenario_id=?",
                               (sid,)).fetchone() is not None

    def delete(self, sid: str) -> bool:
        with self._con() as con:
            con.execute("DELETE FROM scenario_legs WHERE scenario_id=?", (sid,))
            cur = con.execute("DELETE FROM scenarios WHERE scenario_id=?", (sid,))
            return cur.rowcount > 0

    # -- 조회 -----------------------------------------------------------
    def _rebuild(self, con: sqlite3.Connection, sid: str) -> dict | None:
        row = con.execute("SELECT * FROM scenarios WHERE scenario_id=?",
                          (sid,)).fetchone()
        if not row:
            return None
        if row["scenario_json"]:
            sc = json.loads(row["scenario_json"])
        else:
            sc = {
                "scenario_id": row["scenario_id"],
                "scenario_name": row["scenario_name"],
                "created_at": row["created_at"],
                "selected_axis": row["selected_axis"],
                "cargo": {
                    "cargo_type": row["cargo_type"],
                    "vehicle_type": row["vehicle_type"],
                    "quantity": row["quantity"],
                    "quantity_unit": row["quantity_unit"],
                },
                "route": {
                    "origin_node_id": row["origin_node_id"],
                    "origin_location_id": row["origin_location_id"],
                    "origin_name": row["origin_name"],
                    "destination_node_id": row["destination_node_id"],
                    "destination_location_id": row["destination_location_id"],
                    "destination_name": row["destination_name"],
                    "path": json.loads(row["path_json"]) if row["path_json"] else [],
                    "modes": json.loads(row["modes_json"]) if row["modes_json"] else [],
                    "leg_count": row["leg_count"],
                },
                "metrics": {
                    "cost_usd_per_vehicle": row["cost_usd_per_vehicle"],
                    "shipment_cost_usd": row["shipment_cost_usd"],
                    "total_days": row["total_days"],
                    "co2_kg_per_vehicle": row["co2_kg_per_vehicle"],
                    "shipment_co2_kg": row["shipment_co2_kg"],
                    "reliability": row["reliability"],
                    "transfers": row["transfers"],
                    "customs_days": row["customs_days"],
                },
                "schedule": {
                    "etd": row["etd"],
                    "eta": row["eta"],
                    "total_transit_hours": row["total_transit_hours"],
                },
                "trade": {
                    "incoterm": row["incoterm"],
                    "origin_country": row["origin_country"],
                    "destination_country": row["destination_country"],
                    "customs_required": bool(row["customs_required"]),
                },
            }
        legs = con.execute(
            "SELECT * FROM scenario_legs WHERE scenario_id=? ORDER BY sequence",
            (sid,)).fetchall()
        sc["legs"] = [dict(l) for l in legs]
        head = con.execute(
            "SELECT status, is_favorite, cancelled_at, cancel_reason, "
            "closed_at, updated_at FROM scenarios WHERE scenario_id=?",
            (sid,)).fetchone()
        sc["status"] = head["status"]
        sc["is_favorite"] = bool(head["is_favorite"])
        sc["cancelled_at"] = head["cancelled_at"]
        sc["cancel_reason"] = head["cancel_reason"]
        sc["closed_at"] = head["closed_at"]
        sc["updated_at"] = head["updated_at"]
        return sc

    def get(self, sid: str, now=None, tracking: bool = True) -> dict | None:
        with self._con() as con:
            sc = self._rebuild(con, sid)
        if not sc:
            return None
        return enrich(sc, now) if tracking else sc

    def list(self, favorite_only: bool = False, status: str | None = None,
              now=None, tracking: bool = True) -> list[dict]:
        now = now or datetime.now()
        q, args = "SELECT scenario_id FROM scenarios", []
        where = []
        if favorite_only:
            where.append("is_favorite=1")
        if status:
            where.append("status=?")
            args.append(status)
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY etd DESC"
        with self._con() as con:
            ids = [r["scenario_id"] for r in con.execute(q, args)]
            out = []
            for sid in ids:
                sc = self._rebuild(con, sid)
                if sc is None:
                    continue
                out.append(enrich(sc, now) if tracking else sc)
        return out

    def toggle_favorite(self, sid: str) -> bool:
        with self._con() as con:
            con.execute("UPDATE scenarios SET is_favorite = 1 - is_favorite "
                        "WHERE scenario_id=?", (sid,))
            return bool(con.execute("SELECT is_favorite FROM scenarios "
                                    "WHERE scenario_id=?", (sid,)).fetchone()[0])
