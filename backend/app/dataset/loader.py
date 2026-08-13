from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@dataclass
class CarrierDataset:
    carrier_id: str
    carrier_name: str
    group: str
    services: list[dict] = field(default_factory=list)


@dataclass
class Dataset:
    sea: list[CarrierDataset]
    rail: list[CarrierDataset]
    road: list[CarrierDataset]
    air: list[CarrierDataset]
    ports: list[dict]
    road_corridors: list[dict]
    incoterms: list[dict]
    customs_rules: list[dict]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_carrier(path: Path) -> CarrierDataset:
    data = _load_json(path)
    carrier = data["carrier"]
    return CarrierDataset(
        carrier_id=carrier["carrier_id"],
        carrier_name=carrier["carrier_name"],
        group=carrier["group"],
        services=data["services"],
    )


@lru_cache(maxsize=1)
def load_dataset() -> Dataset:
    base = settings.agent_json_dir

    sea = [
        _load_carrier(base / "Ship" / "sea_hmm.json"),
        _load_carrier(base / "Ship" / "sea_wallenius_wilhelmsen.json"),
    ]
    rail = [
        _load_carrier(base / "Train" / "rail_db_cargo.json"),
        _load_carrier(base / "Train" / "rail_rail_cargo_group.json"),
    ]
    road = [
        _load_carrier(base / "Road" / "road_hyundai_glovis.json"),
        _load_carrier(base / "Road" / "road_dsv.json"),
    ]
    air = [
        _load_carrier(base / "Plane" / "air_korean_air_cargo.json"),
        _load_carrier(base / "Plane" / "air_lufthansa_cargo.json"),
    ]

    infra_dir = base / "각종인프라"
    ports = _load_json(infra_dir / "port_infrastructure_agent.json")["ports"]
    road_corridors = _load_json(infra_dir / "road_infrastructure_agent.json")["corridors"]
    incoterms = _load_json(infra_dir / "incoterms.json")["incoterms"]
    customs_rules = _load_json(infra_dir / "customs_rules.json")["rules"]

    return Dataset(
        sea=sea,
        rail=rail,
        road=road,
        air=air,
        ports=ports,
        road_corridors=road_corridors,
        incoterms=incoterms,
        customs_rules=customs_rules,
    )


def reset_cache() -> None:
    """Used by tests that point MLA_AGENT_JSON_DIR at a fixture directory."""
    load_dataset.cache_clear()
