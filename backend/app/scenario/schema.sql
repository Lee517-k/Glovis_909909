-- 시나리오 저장 스키마 (SQLite)
-- Ported from the reference project's backend/glovis_scenario/schema.sql.
-- This project's Data/glovis_merged.db already has matching `scenarios` /
-- `scenario_legs` tables, so ScenarioStore.init() normally no-ops — this
-- file exists as a fallback for a fresh/empty DB.
--
-- progress_percent / shipment_status are NOT stored — only ATD/ATA are
-- stored, and tracking.compute() re-derives progress at read time.

CREATE TABLE scenarios (
    scenario_id           TEXT PRIMARY KEY,
    scenario_name         TEXT NOT NULL,

    status                TEXT NOT NULL DEFAULT 'DRAFT',
        -- DRAFT / CONFIRMED / ACTIVE / CANCELLED / CLOSED
    is_favorite           INTEGER NOT NULL DEFAULT 0,
    cancelled_at          TEXT,
    cancel_reason         TEXT,
    closed_at             TEXT,

    created_at            TEXT NOT NULL,
    updated_at            TEXT,
    selected_axis         TEXT,               -- COST/TIME/CO2/RELIABILITY/BALANCED

    cargo_type            TEXT NOT NULL,
    vehicle_type          TEXT,
    quantity              INTEGER NOT NULL,
    quantity_unit         TEXT DEFAULT 'vehicle',

    origin_node_id        TEXT NOT NULL,
    origin_location_id    TEXT NOT NULL,
    origin_name           TEXT,
    destination_node_id   TEXT NOT NULL,
    destination_location_id TEXT NOT NULL,
    destination_name      TEXT,
    path_json             TEXT,
    modes_json            TEXT,
    leg_count             INTEGER,

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

CREATE TABLE scenario_legs (
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

CREATE INDEX idx_legs_scenario ON scenario_legs(scenario_id);
CREATE INDEX idx_scen_fav      ON scenarios(is_favorite);
CREATE INDEX idx_scen_status   ON scenarios(status);
CREATE INDEX idx_scen_etd      ON scenarios(etd);
