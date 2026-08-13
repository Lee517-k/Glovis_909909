"""senario_ver2/schema.sql 테이블 구조(scenarios/scenario_legs)를 쓰는 스토어.

운송 추적과 운송사 배분 모두 Data/glovis_merged.db의 정본
scenarios/scenario_legs 테이블을 사용한다.

progress_percent/shipment_status는 저장하지 않고 조회 시점에 ATD/ATA로 역산한다
(schema.sql 설계 원칙 — 계산 로직은 app.repositories.tracking_repository /
allocation_repository에 직접 구현).

glovis.db(ct_* 테이블, 운송 시나리오 엔진, 대시보드 알림·보관함·업로드 등 팀원 소관)와는
완전히 다른 파일이라 테이블 이름 충돌이나 서로 간 영향이 없다.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id           TEXT PRIMARY KEY,
    scenario_name         TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'DRAFT',
    is_favorite           INTEGER NOT NULL DEFAULT 0,
    cancelled_at          TEXT,
    cancel_reason         TEXT,
    closed_at             TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT,
    selected_axis         TEXT,
    cargo_type            TEXT NOT NULL,
    vehicle_type          TEXT,
    quantity              INTEGER NOT NULL,
    quantity_unit         TEXT DEFAULT 'vehicle',
    origin_node_id        TEXT NOT NULL,
    origin_location_id    TEXT NOT NULL,
    origin_name            TEXT,
    destination_node_id   TEXT NOT NULL,
    destination_location_id TEXT NOT NULL,
    destination_name      TEXT,
    path_json             TEXT,
    modes_json             TEXT,
    leg_count              INTEGER,
    cost_usd_per_vehicle  REAL,
    shipment_cost_usd     REAL,
    total_days            REAL,
    co2_kg_per_vehicle    REAL,
    shipment_co2_kg       REAL,
    reliability           REAL,
    transfers             INTEGER,
    customs_days          REAL,
    etd                   TEXT NOT NULL,
    eta                   TEXT NOT NULL,
    total_transit_hours   REAL,
    incoterm              TEXT,
    origin_country        TEXT,
    destination_country   TEXT,
    customs_required      INTEGER,
    scenario_json         TEXT
);

CREATE TABLE IF NOT EXISTS scenario_legs (
    leg_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id           TEXT NOT NULL REFERENCES scenarios(scenario_id),
    sequence              INTEGER NOT NULL,
    mode                  TEXT NOT NULL,
    carrier_id            TEXT NOT NULL,
    carrier_name          TEXT NOT NULL,
    service_id            TEXT NOT NULL,
    service_tier          TEXT,
    source_dataset        TEXT,
    origin_node_id        TEXT NOT NULL,
    origin_location_id    TEXT,
    origin_name           TEXT,
    destination_node_id   TEXT NOT NULL,
    destination_location_id TEXT,
    destination_name      TEXT,
    distance_km           REAL,
    cost_usd_per_vehicle  REAL,
    transit_hours         REAL,
    co2_kg_per_vehicle    REAL,
    reliability           REAL,
    etd                   TEXT NOT NULL,
    eta                   TEXT NOT NULL,
    atd                   TEXT,
    ata                   TEXT,
    expected_delay_hours  REAL,
    delay_reason          TEXT,
    UNIQUE(scenario_id, sequence)
);

CREATE INDEX IF NOT EXISTS idx_legs_scenario ON scenario_legs(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scen_fav      ON scenarios(is_favorite);
CREATE INDEX IF NOT EXISTS idx_scen_status   ON scenarios(status);
CREATE INDEX IF NOT EXISTS idx_scen_etd      ON scenarios(etd);
"""


class ScenarioTrackingStore:
    def __init__(self, db_path):
        self._db_path = db_path
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def list_scenarios(self, statuses: tuple[str, ...] | None = None) -> list[dict]:
        sql, params = "SELECT * FROM scenarios", []
        if statuses:
            sql += f" WHERE status IN ({','.join('?' * len(statuses))})"
            params.extend(statuses)
        sql += " ORDER BY etd DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def get_scenario(self, scenario_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM scenarios WHERE scenario_id=?", (scenario_id,)).fetchone()
            return dict(row) if row else None

    def get_legs(self, scenario_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scenario_legs WHERE scenario_id=? ORDER BY sequence", (scenario_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def legs_for_many(self, scenario_ids: list[str]) -> dict[str, list[dict]]:
        """목록 조회 시 N+1 방지용 — 여러 시나리오의 구간을 한 번에."""
        if not scenario_ids:
            return {}
        marks = ",".join("?" * len(scenario_ids))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM scenario_legs WHERE scenario_id IN ({marks}) ORDER BY scenario_id, sequence",
                scenario_ids,
            ).fetchall()
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(r["scenario_id"], []).append(dict(r))
        return out

    def set_leg_event(self, scenario_id: str, sequence: int, field: str, at: str) -> bool:
        """atd/ata 기록 (출발/도착 이벤트)."""
        assert field in ("atd", "ata")
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE scenario_legs SET {field}=? WHERE scenario_id=? AND sequence=?",
                (at, scenario_id, sequence),
            )
            return cur.rowcount > 0



_store: ScenarioTrackingStore | None = None
_history_store: ScenarioTrackingStore | None = None


def get_scenario_tracking_store() -> ScenarioTrackingStore:
    """병합 DB의 시나리오 데이터를 운송 추적에 제공한다."""
    global _store
    if _store is None:
        from app.core.config import settings
        settings.merged_db_path.parent.mkdir(parents=True, exist_ok=True)
        _store = ScenarioTrackingStore(str(settings.merged_db_path))
    return _store


def get_allocation_history_store() -> ScenarioTrackingStore:
    """병합 DB의 동일한 시나리오 데이터를 운송사 배분에 제공한다."""
    global _history_store
    if _history_store is None:
        from app.core.config import settings
        settings.merged_db_path.parent.mkdir(parents=True, exist_ok=True)
        _history_store = ScenarioTrackingStore(str(settings.merged_db_path))
    return _history_store


def reset_scenario_tracking_store() -> None:
    global _store
    _store = None
