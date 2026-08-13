"""Control Tower 전용 SQLite 스토어.

'운송 추적'/'운송사 배분' 및 그 밖의 화면(대시보드 알림, 제안서 보관함,
데이터 업로드)이 쓰는 테이블을 담당한다.

- 기존 시나리오/제안 테이블(app/db/sqlite_store.py)과 **같은 DB 파일**
  (settings.db_path)을 쓴다. 요구사항인 "하나의 DB에 저장"을 만족시키면서,
  테이블 이름은 ct_ 접두사로 분리해 충돌을 피한다.
- 최초 기동 시 테이블이 비어 있으면 control_tower_seed 의 더미 데이터를
  한 번만 적재한다(seed_if_empty).
"""

from __future__ import annotations

import json
import math
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone

from app.core.config import settings
from app.dataset import control_tower_seed as seed

_SCHEMA = """
-- 노드(항만/공항/내륙거점): 지도 좌표와 지역권의 원천
CREATE TABLE IF NOT EXISTS ct_nodes (
    node_id     TEXT PRIMARY KEY,
    name_ko     TEXT NOT NULL,
    name_en     TEXT,
    lng         REAL NOT NULL,
    lat         REAL NOT NULL,
    node_type   TEXT,
    country     TEXT,
    region_id   TEXT
);

-- 지역권(운송사 배분 탭)
CREATE TABLE IF NOT EXISTS ct_regions (
    region_id   TEXT PRIMARY KEY,
    region_name TEXT NOT NULL,
    sort_order  INTEGER,
    is_tab      INTEGER DEFAULT 1
);

-- 운송사 마스터
CREATE TABLE IF NOT EXISTS ct_carriers (
    carrier_id        TEXT PRIMARY KEY,
    carrier_name      TEXT NOT NULL,
    description       TEXT,
    modes             TEXT,           -- CSV: sea,rail,air,truck,express
    region_id         TEXT,
    grade             TEXT,           -- A~E
    grade_kind        TEXT,           -- cii | esg
    on_time_pct       INTEGER,
    contract_left_pct REAL,           -- 계약 잔량(%) · NULL이면 자가운송
    status_tone       TEXT,           -- ok | warn | danger | blue
    status_label      TEXT,
    color             TEXT
);

-- 지역권 × 운송사 배분 실적(최근 90일). HHI는 share_pct로 서버에서 계산.
CREATE TABLE IF NOT EXISTS ct_allocations (
    alloc_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id    TEXT NOT NULL,
    carrier_id   TEXT,               -- NULL이면 '기타' 집계 버킷
    display_name TEXT,
    volume       REAL,
    volume_unit  TEXT,
    spend_100m   REAL,               -- 집행액(억원)
    share_pct    REAL
);

-- 거점별 물량(지도 버블)
CREATE TABLE IF NOT EXISTS ct_hub_volumes (
    node_id      TEXT PRIMARY KEY,
    volume       REAL,
    volume_unit  TEXT,
    primary_mode TEXT,
    label        TEXT,
    radius       INTEGER
);

-- 화물(운송) 마스터
CREATE TABLE IF NOT EXISTS ct_shipments (
    shipment_id      TEXT PRIMARY KEY,
    cargo_name       TEXT,
    cargo_weight_kg  REAL,
    origin_node      TEXT,
    dest_node        TEXT,
    modes            TEXT,           -- CSV
    progress_pct     INTEGER,
    status           TEXT,           -- IN_TRANSIT/DELAYED/CUSTOMS_HOLD/ARRIVING/PLANNED/COMPLETED
    eta_planned      TEXT,           -- ISO datetime
    eta_forecast     TEXT,           -- ISO datetime (지연 시 계획과 다름)
    risk_score       REAL,
    risk_level       TEXT,
    esg_grade        TEXT,
    cii_grade        TEXT,
    co2_kg           REAL,
    carrier_ids      TEXT,           -- CSV
    region_id        TEXT,
    current_node     TEXT,
    current_label    TEXT,
    transship_wait   INTEGER DEFAULT 0,
    updated_at       TEXT
);

-- 화물별 구간 타임라인
CREATE TABLE IF NOT EXISTS ct_shipment_segments (
    segment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id  TEXT NOT NULL,
    sequence     INTEGER,
    from_node    TEXT,
    to_node      TEXT,
    mode         TEXT,
    carrier_id   TEXT,
    kind         TEXT,               -- MOVE | CUSTOMS | HANDOVER
    title        TEXT,
    note         TEXT,
    planned_days REAL,
    actual_days  REAL,
    state        TEXT                -- done | active | pending
);

-- 화물별 AI 알림
CREATE TABLE IF NOT EXISTS ct_shipment_alerts (
    alert_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    shipment_id TEXT NOT NULL,
    severity    TEXT,                -- CRITICAL | WARNING | INFO
    category    TEXT,
    title       TEXT,
    message     TEXT,
    action_label TEXT,
    resolved    INTEGER DEFAULT 0,
    created_at  TEXT
);

-- 컨트롤타워 전역 알림(대시보드)
CREATE TABLE IF NOT EXISTS ct_ops_alerts (
    alert_id    TEXT PRIMARY KEY,
    level       TEXT,                -- critical | warning | info
    label       TEXT,
    title       TEXT,
    body        TEXT,
    action_label TEXT,
    action_page TEXT,
    created_at  TEXT,
    dismissed   INTEGER DEFAULT 0
);

-- 제안서 보관함
CREATE TABLE IF NOT EXISTS ct_saved_proposals (
    proposal_id  TEXT PRIMARY KEY,
    title        TEXT,
    cost_amount  REAL,
    currency     TEXT,
    days         REAL,
    esg_grade    TEXT,
    tag_tone     TEXT,
    tag_label    TEXT,
    modes_json   TEXT,
    created_at   TEXT
);

-- 데이터 업로드 배치(컬럼 매핑/검증 결과 보관)
CREATE TABLE IF NOT EXISTS ct_upload_batches (
    batch_id     TEXT PRIMARY KEY,
    filename     TEXT,
    row_count    INTEGER,
    column_count INTEGER,
    status       TEXT,               -- MAPPED | COMMITTED
    mapping_json TEXT,
    issues_json  TEXT,
    impact_json  TEXT,
    created_at   TEXT,
    committed_at TEXT
);

CREATE INDEX IF NOT EXISTS ix_ct_seg_shipment   ON ct_shipment_segments(shipment_id);
CREATE INDEX IF NOT EXISTS ix_ct_alert_shipment ON ct_shipment_alerts(shipment_id);
CREATE INDEX IF NOT EXISTS ix_ct_alloc_region   ON ct_allocations(region_id);
CREATE INDEX IF NOT EXISTS ix_ct_ship_status    ON ct_shipments(status);
"""

# 활성(진행중)으로 집계하는 상태들 — KPI '진행중'의 정의
ACTIVE_STATUSES = ("IN_TRANSIT", "DELAYED", "CUSTOMS_HOLD", "ARRIVING")


def haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """두 좌표 사이의 대권 거리(km). 구간 거리 표시에 쓴다."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class ControlTowerStore:
    def __init__(self, db_path):
        self._db_path = db_path
        self._lock = threading.Lock()
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
        self.seed_if_empty()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 시드
    # ------------------------------------------------------------------
    def seed_if_empty(self) -> bool:
        """ct_shipments 가 비어 있을 때만 더미 데이터를 적재한다."""
        with self._lock, self._connect() as conn:
            if conn.execute("SELECT COUNT(*) c FROM ct_shipments").fetchone()["c"] > 0:
                return False
            self._seed(conn)
            return True

    def _seed(self, conn: sqlite3.Connection) -> None:
        now = datetime.now(timezone.utc)
        today = date.today()

        conn.executemany("INSERT OR REPLACE INTO ct_nodes VALUES (?,?,?,?,?,?,?,?)", seed.NODES)
        conn.executemany("INSERT OR REPLACE INTO ct_regions VALUES (?,?,?,?)", seed.REGIONS)
        conn.executemany("INSERT OR REPLACE INTO ct_carriers VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", seed.CARRIERS)
        conn.executemany(
            "INSERT INTO ct_allocations (region_id,carrier_id,display_name,volume,volume_unit,spend_100m,share_pct)"
            " VALUES (?,?,?,?,?,?,?)",
            seed.ALLOCATIONS,
        )
        conn.executemany("INSERT OR REPLACE INTO ct_hub_volumes VALUES (?,?,?,?,?,?)", seed.HUB_VOLUMES)

        # 화물: eta 오프셋(일)을 시드 적재일 기준 절대 시각으로 변환한다.
        for s in seed.SHIPMENTS:
            (sid, cargo, kg, frm, to, modes, pct, status, eta_off, eta_time, fc_off,
             risk, risk_lv, esg, cii, co2, carriers, region, cur_node, cur_label, tswait) = s
            eta_planned = _at(today, eta_off, eta_time)
            eta_forecast = _at(today, fc_off, eta_time) if fc_off is not None else eta_planned
            conn.execute(
                """INSERT OR REPLACE INTO ct_shipments
                (shipment_id,cargo_name,cargo_weight_kg,origin_node,dest_node,modes,progress_pct,status,
                 eta_planned,eta_forecast,risk_score,risk_level,esg_grade,cii_grade,co2_kg,carrier_ids,
                 region_id,current_node,current_label,transship_wait,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, cargo, kg, frm, to, modes, pct, status, eta_planned, eta_forecast, risk, risk_lv,
                 esg, cii, co2, carriers, region, cur_node, cur_label, tswait, now.isoformat()),
            )

        for sid, legs in seed.SEGMENTS.items():
            for (seq, frm, to, mode, carrier, plan, actual, state, kind, title, note) in legs:
                conn.execute(
                    """INSERT INTO ct_shipment_segments
                    (shipment_id,sequence,from_node,to_node,mode,carrier_id,kind,title,note,planned_days,actual_days,state)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (sid, seq, frm, to, mode, carrier, kind, title, note, plan, actual, state),
                )

        for (sid, sev, cat, title, msg, hours_ago, resolved, action) in seed.SHIPMENT_ALERTS:
            conn.execute(
                """INSERT INTO ct_shipment_alerts
                (shipment_id,severity,category,title,message,action_label,resolved,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (sid, sev, cat, title, msg, action, resolved, (now - timedelta(hours=hours_ago)).isoformat()),
            )

        for (aid, level, label, title, body, hours_ago, action, page) in seed.OPS_ALERTS:
            conn.execute(
                """INSERT OR REPLACE INTO ct_ops_alerts
                (alert_id,level,label,title,body,action_label,action_page,created_at,dismissed)
                VALUES (?,?,?,?,?,?,?,?,0)""",
                (aid, level, label, title, body, action, page, (now - timedelta(hours=hours_ago)).isoformat()),
            )

        for (pid, title, cost, cur, days, esg, tone, label, modes_json) in seed.SAVED_PROPOSALS:
            conn.execute(
                """INSERT OR REPLACE INTO ct_saved_proposals
                (proposal_id,title,cost_amount,currency,days,esg_grade,tag_tone,tag_label,modes_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (pid, title, cost, cur, days, esg, tone, label, modes_json, now.isoformat()),
            )

    # ------------------------------------------------------------------
    # 조회 (운송 추적)
    # ------------------------------------------------------------------
    def list_shipments(
        self,
        q: str | None = None,
        status: str | None = None,
        mode: str | None = None,
        region_id: str | None = None,
        scope: str = "active",
        sort: str = "eta",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """화물 목록 검색/필터/정렬.

        q  : 운송번호·화물명·출발지/도착지(한글·영문·코드)·현재위치·운송사명을 부분 일치 검색.
        scope: active(진행중) | all | completed | planned
        sort : eta | -eta | progress | -progress | risk | -risk | id
        반환: (행 목록, 필터 조건 하의 전체 건수)
        """
        where, params = [], []

        if scope == "active":
            where.append(f"s.status IN ({','.join('?' * len(ACTIVE_STATUSES))})")
            params.extend(ACTIVE_STATUSES)
        elif scope in ("completed", "planned"):
            where.append("s.status = ?")
            params.append("COMPLETED" if scope == "completed" else "PLANNED")

        if status:
            marks = [x.strip().upper() for x in status.split(",") if x.strip()]
            if marks:
                where.append(f"s.status IN ({','.join('?' * len(marks))})")
                params.extend(marks)

        if mode:
            # modes 는 CSV 이므로 각 모드를 콤마 경계까지 포함해 비교한다.
            marks = [m.strip().lower() for m in mode.split(",") if m.strip()]
            if marks:
                where.append("(" + " OR ".join(["(',' || s.modes || ',') LIKE ?"] * len(marks)) + ")")
                params.extend([f"%,{m},%" for m in marks])

        if region_id:
            where.append("s.region_id = ?")
            params.append(region_id)

        if q:
            like = f"%{q.strip()}%"
            where.append(
                "(s.shipment_id LIKE ? OR s.cargo_name LIKE ? OR s.current_label LIKE ?"
                " OR o.name_ko LIKE ? OR o.name_en LIKE ? OR s.origin_node LIKE ?"
                " OR d.name_ko LIKE ? OR d.name_en LIKE ? OR s.dest_node LIKE ?"
                " OR EXISTS (SELECT 1 FROM ct_carriers c WHERE (',' || s.carrier_ids || ',') LIKE ('%,' || c.carrier_id || ',%')"
                "            AND c.carrier_name LIKE ?))"
            )
            params.extend([like] * 10)

        order = {
            "eta": "s.eta_forecast ASC",
            "-eta": "s.eta_forecast DESC",
            "progress": "s.progress_pct ASC",
            "-progress": "s.progress_pct DESC",
            "risk": "s.risk_score ASC",
            "-risk": "s.risk_score DESC",
            "id": "s.shipment_id ASC",
        }.get(sort, "s.eta_forecast ASC")

        clause = ("WHERE " + " AND ".join(where)) if where else ""
        base = (
            "FROM ct_shipments s"
            " LEFT JOIN ct_nodes o ON o.node_id = s.origin_node"
            " LEFT JOIN ct_nodes d ON d.node_id = s.dest_node "
            + clause
        )
        with self._connect() as conn:
            total = conn.execute(f"SELECT COUNT(*) c {base}", params).fetchone()["c"]
            rows = conn.execute(
                "SELECT s.*, o.name_ko origin_name, d.name_ko dest_name,"
                " (SELECT COUNT(*) FROM ct_shipment_alerts a WHERE a.shipment_id = s.shipment_id"
                "   AND a.resolved = 0 AND a.severity IN ('CRITICAL','WARNING')) open_alerts,"
                " EXISTS (SELECT 1 FROM ct_shipment_alerts a WHERE a.shipment_id = s.shipment_id"
                "   AND a.resolved = 0 AND a.severity = 'CRITICAL') open_critical "
                f"{base} ORDER BY {order} LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows], total

    def get_shipment(self, shipment_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT s.*, o.name_ko origin_name, d.name_ko dest_name, c.name_ko current_name,"
                " c.lng current_lng, c.lat current_lat"
                " FROM ct_shipments s"
                " LEFT JOIN ct_nodes o ON o.node_id = s.origin_node"
                " LEFT JOIN ct_nodes d ON d.node_id = s.dest_node"
                " LEFT JOIN ct_nodes c ON c.node_id = s.current_node"
                " WHERE s.shipment_id = ?",
                (shipment_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_segments(self, shipment_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT g.*, f.name_ko from_name, f.lng from_lng, f.lat from_lat,"
                " t.name_ko to_name, t.lng to_lng, t.lat to_lat,"
                " cr.carrier_name, cr.on_time_pct, cr.grade carrier_grade, cr.grade_kind"
                " FROM ct_shipment_segments g"
                " LEFT JOIN ct_nodes f ON f.node_id = g.from_node"
                " LEFT JOIN ct_nodes t ON t.node_id = g.to_node"
                " LEFT JOIN ct_carriers cr ON cr.carrier_id = g.carrier_id"
                " WHERE g.shipment_id = ? ORDER BY g.sequence",
                (shipment_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_shipment_alerts(self, shipment_id: str, only_open: bool = False) -> list[dict]:
        sql = "SELECT * FROM ct_shipment_alerts WHERE shipment_id = ?"
        if only_open:
            sql += " AND resolved = 0"
        sql += " ORDER BY resolved ASC, created_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, (shipment_id,)).fetchall()]

    def resolve_shipment_alert(self, alert_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE ct_shipment_alerts SET resolved = 1 WHERE alert_id = ?", (alert_id,))
            return cur.rowcount > 0

    def tracking_counters(self) -> dict:
        """KPI 5종을 SQL 집계로 한 번에 구한다."""
        marks = ",".join("?" * len(ACTIVE_STATUSES))
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT
                  COUNT(*) active_total,
                  SUM(CASE WHEN status = 'DELAYED' OR eta_forecast > eta_planned THEN 1 ELSE 0 END) delayed,
                  SUM(CASE WHEN transship_wait = 1 THEN 1 ELSE 0 END) transship_wait,
                  SUM(CASE WHEN substr(eta_forecast,1,10) = ? THEN 1 ELSE 0 END) arriving_today,
                  SUM(CASE WHEN EXISTS (SELECT 1 FROM ct_shipment_alerts a
                        WHERE a.shipment_id = ct_shipments.shipment_id AND a.resolved = 0
                          AND a.severity IN ('CRITICAL','WARNING')) THEN 1 ELSE 0 END) watch
                FROM ct_shipments WHERE status IN ({marks})
                """,
                [today, *ACTIVE_STATUSES],
            ).fetchone()
            on_time = conn.execute(
                "SELECT AVG(CASE WHEN eta_forecast <= eta_planned THEN 1.0 ELSE 0.0 END) r"
                " FROM ct_shipments WHERE status != 'PLANNED'"
            ).fetchone()["r"]
        out = {k: (row[k] or 0) for k in row.keys()}
        out["on_time_rate"] = round((on_time or 0) * 100, 1)
        return out

    # ------------------------------------------------------------------
    # 조회 (운송사 배분)
    # ------------------------------------------------------------------
    def list_regions(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ct_regions WHERE is_tab = 1 ORDER BY sort_order").fetchall()]

    def list_allocations(self, region_id: str | None = None) -> list[dict]:
        sql = ("SELECT a.*, r.region_name, c.color, c.carrier_name, c.status_tone"
               " FROM ct_allocations a"
               " JOIN ct_regions r ON r.region_id = a.region_id"
               " LEFT JOIN ct_carriers c ON c.carrier_id = a.carrier_id")
        params: list = []
        if region_id:
            sql += " WHERE a.region_id = ?"
            params.append(region_id)
        sql += " ORDER BY r.sort_order, a.share_pct DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def list_carriers(self, region_id: str | None = None, mode: str | None = None) -> list[dict]:
        """운송사 현황 표.

        물량/집행액/비중은 '조회 대상 지역권' 기준으로 집계한다.
        지역권 필터가 없으면 그 운송사의 주력 지역권(c.region_id) 기준이며,
        모든 지역권을 합한 값은 total_volume 으로 따로 제공한다.
        (한 운송사가 여러 지역권에 걸치는 경우 비중이 뒤섞이는 것을 막기 위함)
        """
        # SELECT 절의 ? 가 WHERE 절보다 먼저 오므로 파라미터 순서를 분리해서 관리한다.
        select_params = [region_id, region_id, region_id, region_id]
        sql = (
            "SELECT c.*, r.region_name,"
            " (SELECT SUM(volume) FROM ct_allocations a"
            "   WHERE a.carrier_id = c.carrier_id AND a.region_id = COALESCE(?, c.region_id)) volume,"
            " (SELECT volume_unit FROM ct_allocations a"
            "   WHERE a.carrier_id = c.carrier_id AND a.region_id = COALESCE(?, c.region_id) LIMIT 1) volume_unit,"
            " (SELECT SUM(spend_100m) FROM ct_allocations a"
            "   WHERE a.carrier_id = c.carrier_id AND a.region_id = COALESCE(?, c.region_id)) spend_100m,"
            " (SELECT SUM(share_pct) FROM ct_allocations a"
            "   WHERE a.carrier_id = c.carrier_id AND a.region_id = COALESCE(?, c.region_id)) share_pct,"
            " (SELECT SUM(volume) FROM ct_allocations a WHERE a.carrier_id = c.carrier_id) total_volume"
            " FROM ct_carriers c LEFT JOIN ct_regions r ON r.region_id = c.region_id"
        )
        where, params = [], []
        if region_id:
            # 해당 지역권에 실제로 물량이 있는 운송사까지 포함한다.
            where.append("EXISTS (SELECT 1 FROM ct_allocations a"
                         " WHERE a.carrier_id = c.carrier_id AND a.region_id = ?)")
            params.append(region_id)
        if mode:
            marks = [m.strip().lower() for m in mode.split(",") if m.strip()]
            if marks:
                where.append("(" + " OR ".join(["(',' || c.modes || ',') LIKE ?"] * len(marks)) + ")")
                params.extend([f"%,{m},%" for m in marks])
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY share_pct DESC, c.carrier_name"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, [*select_params, *params]).fetchall()]

    def list_hub_volumes(self, region_id: str | None = None) -> list[dict]:
        sql = ("SELECT h.*, n.name_ko, n.name_en, n.lng, n.lat, n.region_id, n.node_type"
               " FROM ct_hub_volumes h JOIN ct_nodes n ON n.node_id = h.node_id")
        params: list = []
        if region_id:
            sql += " WHERE n.region_id = ?"
            params.append(region_id)
        sql += " ORDER BY h.volume DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def list_nodes(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM ct_nodes ORDER BY node_id").fetchall()]

    # ------------------------------------------------------------------
    # 조회 (대시보드 알림 / 보관함 / 업로드)
    # ------------------------------------------------------------------
    def list_ops_alerts(self, include_dismissed: bool = False) -> list[dict]:
        sql = "SELECT * FROM ct_ops_alerts"
        if not include_dismissed:
            sql += " WHERE dismissed = 0"
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql).fetchall()]

    def dismiss_ops_alert(self, alert_id: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "UPDATE ct_ops_alerts SET dismissed = 1 WHERE alert_id = ?", (alert_id,)).rowcount > 0

    def list_saved_proposals(self) -> list[dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM ct_saved_proposals ORDER BY created_at DESC").fetchall()]

    def save_proposal(self, payload: dict) -> dict:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ct_saved_proposals
                (proposal_id,title,cost_amount,currency,days,esg_grade,tag_tone,tag_label,modes_json,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (payload["proposal_id"], payload.get("title"), payload.get("cost_amount"),
                 payload.get("currency", "KRW"), payload.get("days"), payload.get("esg_grade"),
                 payload.get("tag_tone", "blue"), payload.get("tag_label", "승인 대기"),
                 json.dumps(payload.get("modes", []), ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat()),
            )
        return payload

    def delete_proposal(self, proposal_id: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "DELETE FROM ct_saved_proposals WHERE proposal_id = ?", (proposal_id,)).rowcount > 0

    def create_upload_batch(self, batch: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO ct_upload_batches
                (batch_id,filename,row_count,column_count,status,mapping_json,issues_json,impact_json,created_at,committed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (batch["batch_id"], batch["filename"], batch["row_count"], batch["column_count"],
                 batch["status"], json.dumps(batch["mapping"], ensure_ascii=False),
                 json.dumps(batch["issues"], ensure_ascii=False),
                 json.dumps(batch["impact"], ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat(), None),
            )

    def get_upload_batch(self, batch_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM ct_upload_batches WHERE batch_id = ?", (batch_id,)).fetchone()
            return dict(row) if row else None

    def commit_upload_batch(self, batch_id: str) -> bool:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "UPDATE ct_upload_batches SET status = 'COMMITTED', committed_at = ? WHERE batch_id = ?",
                (datetime.now(timezone.utc).isoformat(), batch_id)).rowcount > 0

    # ------------------------------------------------------------------
    # 통합 검색 (상단바) — 화물 / 거점 / 운송사 / 보관 제안서
    # ------------------------------------------------------------------
    def global_search(self, q: str, limit: int = 8) -> dict:
        like = f"%{q.strip()}%"
        with self._connect() as conn:
            ships = conn.execute(
                "SELECT s.shipment_id, s.cargo_name, s.status, s.progress_pct, s.eta_forecast,"
                " o.name_ko origin_name, d.name_ko dest_name FROM ct_shipments s"
                " LEFT JOIN ct_nodes o ON o.node_id = s.origin_node"
                " LEFT JOIN ct_nodes d ON d.node_id = s.dest_node"
                " WHERE s.shipment_id LIKE ? OR s.cargo_name LIKE ? OR o.name_ko LIKE ? OR d.name_ko LIKE ?"
                " ORDER BY s.eta_forecast LIMIT ?",
                (like, like, like, like, limit),
            ).fetchall()
            nodes = conn.execute(
                "SELECT node_id, name_ko, name_en, node_type, region_id FROM ct_nodes"
                " WHERE node_id LIKE ? OR name_ko LIKE ? OR name_en LIKE ? LIMIT ?",
                (like, like, like, limit),
            ).fetchall()
            carriers = conn.execute(
                "SELECT carrier_id, carrier_name, description, modes FROM ct_carriers"
                " WHERE carrier_name LIKE ? OR carrier_id LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
            props = conn.execute(
                "SELECT proposal_id, title FROM ct_saved_proposals WHERE proposal_id LIKE ? OR title LIKE ? LIMIT ?",
                (like, like, limit),
            ).fetchall()
        return {
            "shipments": [dict(r) for r in ships],
            "nodes": [dict(r) for r in nodes],
            "carriers": [dict(r) for r in carriers],
            "proposals": [dict(r) for r in props],
        }


def _at(base: date, offset_days: int | None, hhmm: str) -> str:
    """시드 기준일 + 오프셋(일) + 시각 → ISO 문자열."""
    d = base + timedelta(days=offset_days or 0)
    if not hhmm or ":" not in hhmm:
        hhmm = "12:00"
    h, m = hhmm.split(":")
    return datetime(d.year, d.month, d.day, int(h), int(m)).isoformat()


_store: ControlTowerStore | None = None


def get_control_tower_store() -> ControlTowerStore:
    global _store
    if _store is None:
        _store = ControlTowerStore(settings.db_path)
    return _store


def reset_control_tower_store() -> None:
    """테스트에서 DB 경로를 바꾼 뒤 싱글턴을 비우기 위해 사용."""
    global _store
    _store = None
