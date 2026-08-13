from pathlib import Path
import sqlite3

from app.repositories.yp_data_repository import YPDataRepository
from app.api.yp_upload import auto_mappings, validate_rows


def create_test_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute(
        """
        CREATE TABLE carrier_capabilities (
            capability_id TEXT,
            carrier_id TEXT,
            carrier_name TEXT,
            mode TEXT,
            origin_location_id TEXT,
            origin_node_id TEXT,
            origin_name TEXT,
            origin_country TEXT,
            destination_location_id TEXT,
            destination_node_id TEXT,
            destination_name TEXT,
            destination_country TEXT,
            currency TEXT,
            typical_base_rate REAL,
            typical_transit_hours REAL,
            capacity_value REAL,
            capacity_unit TEXT,
            on_time_rate REAL,
            mapping_status TEXT,
            validation_status TEXT,
            validation_score REAL,
            validation_summary TEXT,
            last_validated_at TEXT,
            carries_finished_vehicle INTEGER,
            is_active INTEGER
        )
        """
    )
    connection.executemany(
        "INSERT INTO carrier_capabilities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("cap-1", "carrier-1", "Carrier One", "sea", "KR", None, "Busan", "KR", "DE", None, "Hamburg", "DE", "USD", 100, 240, 10, "TEU", .95, "approved", "verified", 0, "", "2026-08-01", 1, 1),
            ("cap-2", "carrier-1", "Carrier One", "road", "DE", None, "Hamburg", "DE", "CZ", None, "Prague", "CZ", "USD", 200, 10, 20, "ton", .92, "approved", "unverified", 70, "", None, 1, 1),
        ],
    )
    connection.execute("CREATE TABLE scenarios (scenario_id TEXT, status TEXT)")
    connection.execute("INSERT INTO scenarios VALUES ('scenario-1', 'COMPLETED')")
    connection.execute("""CREATE TABLE scenario_legs (
        leg_id TEXT, scenario_id TEXT, carrier_id TEXT, mode TEXT,
        origin_location_id TEXT, origin_node_id TEXT,
        destination_location_id TEXT, destination_node_id TEXT,
        settled_cost_usd_per_vehicle REAL, atd TEXT, ata TEXT
    )""")
    connection.execute("""INSERT INTO scenario_legs VALUES (
        'leg-1','scenario-1','carrier-1','sea','KR',NULL,'DE',NULL,
        100,'2026-08-01T00:00:00','2026-08-11T00:00:00'
    )""")
    connection.commit()
    connection.close()


def test_summary_and_reliability(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    create_test_db(db_path)
    repository = YPDataRepository(db_path)

    summary = repository.summary()
    reliability = repository.reliability()

    assert summary["carriers"] == 1
    assert summary["services"] == 2
    assert reliability[0]["score"] == 65.0
    assert reliability[0]["candidates"] == 1


def test_upload_alias_mapping_and_validation() -> None:
    headers = ["운송수단", "출발지", "도착지", "기본 운임", "소요시간", "정시율"]
    mappings = auto_mappings(headers)
    rows, issues = validate_rows(
        [{"운송수단": "sea", "출발지": "Busan", "도착지": "Hamburg", "기본 운임": "1,200", "소요시간": 360, "정시율": "92%"}],
        mappings,
    )

    assert not issues
    assert rows[0]["typical_base_rate"] == 1200
    assert rows[0]["on_time_rate"] == 0.92
