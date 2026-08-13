from __future__ import annotations

import sqlite3
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
                       COUNT(DISTINCT origin_country)
                         + COUNT(DISTINCT destination_country) AS countries,
                       COUNT(DISTINCT mode) AS modes
                  FROM carrier_capabilities
                 WHERE is_active = 1
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

    def capabilities(self, limit: int = 100, mode: str | None = None) -> list[dict[str, object]]:
        where = ["is_active = 1"]
        params: list[object] = []
        if mode:
            where.append("mode = ?")
            params.append(mode)
        params.append(limit)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT capability_id, carrier_id, carrier_name, mode,
                       COALESCE(origin_name, origin_location_id, '-') AS origin_name,
                       COALESCE(destination_name, destination_location_id, '-') AS destination_name,
                       typical_transit_hours AS transit_hours,
                       on_time_rate, validation_status
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
                       COUNT(*) AS capability_count,
                       ROUND(AVG(COALESCE(validation_score, 0)), 1) AS score,
                       SUM(CASE WHEN validation_status = 'verified' THEN 1 ELSE 0 END) AS verified_count,
                       SUM(CASE WHEN validation_status != 'verified' THEN 1 ELSE 0 END) AS review_count,
                       MAX(last_validated_at) AS last_validated_at
                  FROM carrier_capabilities
                 WHERE is_active = 1
                 GROUP BY carrier_id, carrier_name
                 ORDER BY score DESC, carrier_name
                """
            ).fetchall()
        return [dict(row) for row in rows]

