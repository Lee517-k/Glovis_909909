from __future__ import annotations

import sqlite3
import hashlib
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "Data" / "glovis_merged.db"


class YPDataRepository:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.db_path}")
        connection = sqlite3.connect(f"file:{self.db_path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def summary(self) -> dict[str, object]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(DISTINCT carrier_id) AS carriers,
                       COUNT(*) AS services,
                       COUNT(DISTINCT origin_location_id)
                         + COUNT(DISTINCT destination_location_id) AS locations,
                       COALESCE(SUM(carries_finished_vehicle), 0) AS finished_vehicle,
                       SUM(CASE WHEN validation_status != 'verified' THEN 1 ELSE 0 END) AS unverified
                  FROM carrier_capabilities
                 WHERE is_active = 1 AND validation_status != 'excluded'
                """
            ).fetchone()
            modes = connection.execute(
                """
                SELECT mode, COUNT(*) AS count
                  FROM carrier_capabilities
                 WHERE is_active = 1
                 GROUP BY mode
                 ORDER BY count DESC
                """
            ).fetchall()
        result = dict(row) if row else {}
        result["mode_counts"] = [dict(item) for item in modes]
        return result

    def capabilities(self, limit: int = 1000, mode: str | None = None, approval_status: str = "approved") -> list[dict[str, object]]:
        where = ["is_active = 1", "validation_status != 'excluded'"]
        params: list[object] = []
        if mode:
            where.append("mode = ?")
            params.append(mode)
        if approval_status == "approved":
            where.append("mapping_status = 'approved'")
        elif approval_status == "unapproved":
            where.append("COALESCE(mapping_status, '') != 'approved'")
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT capability_id, carrier_id, carrier_name, mode,
                       COALESCE(origin_name, origin_location_id, '-') AS origin_name,
                       COALESCE(destination_name, destination_location_id, '-') AS destination_name,
                       currency, typical_base_rate AS base_rate,
                       typical_transit_hours AS transit_hours,
                       capacity_value, capacity_unit, on_time_rate, validation_status
                  FROM carrier_capabilities
                 WHERE {' AND '.join(where)}
                 ORDER BY carrier_name, capability_id
                 LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def reliability(self) -> list[dict[str, object]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT carrier_id,
                       carrier_name,
                       ROUND(AVG(COALESCE(validation_score, 0)), 1) AS score,
                       CASE WHEN SUM(CASE WHEN validation_status != 'verified' THEN 1 ELSE 0 END) = 0
                            THEN 'verified'
                            WHEN SUM(CASE WHEN validation_status = 'verified' THEN 1 ELSE 0 END) > 0
                            THEN 'review' ELSE 'unverified' END AS status,
                       SUM(CASE WHEN validation_status = 'verified' THEN 1 ELSE 0 END) AS validated_count,
                       SUM(CASE WHEN validation_status != 'verified' THEN 1 ELSE 0 END) AS candidates
                  FROM carrier_capabilities
                 WHERE is_active = 1 AND mapping_status = 'approved' AND validation_status != 'excluded'
                 GROUP BY carrier_id, carrier_name
                 ORDER BY score DESC, carrier_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def reliability_detail(self, carrier_id: str) -> dict[str, object] | None:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT capability_id, carrier_id, carrier_name,
                       COALESCE(origin_name, origin_location_id, '-') AS origin_name,
                       COALESCE(destination_name, destination_location_id, '-') AS destination_name,
                       typical_base_rate, typical_transit_hours, validation_status,
                       COALESCE(validation_score, 0) AS validation_score,
                       COALESCE(validation_summary, '') AS validation_summary
                  FROM carrier_capabilities
                 WHERE carrier_id = ? AND is_active = 1
                   AND mapping_status = 'approved' AND validation_status != 'excluded'
                 ORDER BY origin_name, destination_name, capability_id
                """,
                (carrier_id,),
            ).fetchall()
            historical_count = connection.execute(
                "SELECT COUNT(*) FROM scenario_legs WHERE carrier_id = ? OR carrier_name = ?",
                (carrier_id, rows[0]["carrier_name"] if rows else ""),
            ).fetchone()[0] if rows else 0
        if not rows:
            return None
        metrics: list[dict[str, object]] = []
        verified_metrics: list[dict[str, object]] = []
        for row in rows:
            verified = row["validation_status"] == "verified"
            metric = {
                "capability_id": row["capability_id"],
                "metric": f'{row["origin_name"]} → {row["destination_name"]}',
                "db_value": " · ".join([
                    f'운임 ${row["typical_base_rate"]:,.1f}' if row["typical_base_rate"] is not None else "운임 미등록",
                    f'소요 {row["typical_transit_hours"]:.1f}시간' if row["typical_transit_hours"] is not None else "일정 미등록",
                ]),
                "actual_value": "과거 운송 실적 연결 대기" if not verified else "검증 완료 데이터",
                "error": "산정 불가" if not verified else "허용 범위",
                "verdict": "허용 범위" if verified else "검증 필요",
                "reason": row["validation_summary"] or ("담당자가 검증 완료로 승인했습니다." if verified else "추가 운송 근거가 필요합니다."),
                "action": "검증 완료" if verified else "보정 후보 유지",
            }
            (verified_metrics if verified else metrics).append(metric)
        total = len(rows)
        verified_count = len(verified_metrics)
        score = round(sum(float(row["validation_score"] or 0) for row in rows) / total, 1)
        coverage = round(verified_count / total * 100, 1)
        return {
            "carrier_id": carrier_id,
            "carrier_name": rows[0]["carrier_name"],
            "score": score,
            "status": "verified" if verified_count == total else "review" if verified_count else "unverified",
            "validated_count": verified_count,
            "candidates": total - verified_count,
            "hit_rate": coverage,
            "cost_error": 0.0,
            "days_error": 0.0,
            "coverage": coverage,
            "historical_count": historical_count,
            "verified_capability_count": verified_count,
            "total_capability_count": total,
            "metrics": metrics,
            "verified_metrics": verified_metrics,
            "impact": f"승인 역량 {total}개 중 {verified_count}개가 검증 완료 상태입니다.",
        }

    def update_validation_actions(self, carrier_id: str, actions: list[tuple[str, str]]) -> int:
        connection = sqlite3.connect(self.db_path)
        try:
            updated = 0
            now = datetime.now(timezone.utc).isoformat()
            for capability_id, status in actions:
                cursor = connection.execute(
                    "UPDATE carrier_capabilities SET validation_status=?, last_validated_at=?, updated_at=? WHERE carrier_id=? AND capability_id=? AND is_active=1",
                    (status, now, now, carrier_id, capability_id),
                )
                updated += cursor.rowcount
            connection.commit()
            return updated
        finally:
            connection.close()

    def insert_upload(self, carrier_name: str, rows: list[dict[str, object]], source_file: str) -> int:
        carrier_id = "".join(character if character.isalnum() else "_" for character in carrier_name.upper()).strip("_")
        now = datetime.now(timezone.utc).isoformat()
        connection = sqlite3.connect(self.db_path)
        try:
            for index, row in enumerate(rows):
                raw_id = f"{carrier_id}:{row.get('mode')}:{row.get('origin_name')}:{row.get('destination_name')}:{index}"
                capability_id = f"CAP-{carrier_id}-{hashlib.sha1(raw_id.encode()).hexdigest()[:10].upper()}"
                connection.execute(
                    """
                    INSERT INTO carrier_capabilities(
                        capability_id, carrier_id, carrier_name, mode, origin_name, destination_name,
                        currency, typical_base_rate, typical_transit_hours, capacity_value, capacity_unit,
                        on_time_rate, mapping_status, validation_status, validation_score, is_active,
                        created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,'USD',?,?,?,?,?,'approved','unverified',0,1,?,?)
                    ON CONFLICT(capability_id) DO UPDATE SET
                        typical_base_rate=excluded.typical_base_rate,
                        typical_transit_hours=excluded.typical_transit_hours,
                        capacity_value=excluded.capacity_value,
                        capacity_unit=excluded.capacity_unit,
                        on_time_rate=excluded.on_time_rate,
                        updated_at=excluded.updated_at
                    """,
                    (capability_id, carrier_id, carrier_name, str(row.get("mode", "")).lower(), row.get("origin_name"), row.get("destination_name"), row.get("typical_base_rate"), row.get("typical_transit_hours"), row.get("capacity_value"), row.get("capacity_unit"), row.get("on_time_rate"), now, now),
                )
            connection.commit()
            return len(rows)
        finally:
            connection.close()
