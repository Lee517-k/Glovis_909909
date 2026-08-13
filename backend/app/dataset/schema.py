"""Normalized service record shared by the dataset loader and the deterministic
route search.

Ported from the reference project's llm-agent/schema.py. Every field the
route search / ranking layer needs is described here so neither of those
modules has to know anything about the raw JSON shape of the underlying
carrier-service dataset.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NormalizedService:
    service_id: str
    carrier_id: str
    carrier_name: str
    mode: str  # sea | rail | road | air
    origin: str  # location_id
    destination: str  # location_id
    cost_usd: float  # all-in, USD, per vehicle (SEDAN-equivalent baseline; see ceu.py)
    cost_unit: str  # "vehicle" for this dataset
    transit_days: float
    wait_days: float
    total_days: float  # transit_days + wait_days
    reliability_score: float
    co2_kg: Optional[float]
    available_capacity: Optional[float]
    cargo_ok: bool = True
    vehicle_class: Optional[str] = None  # unused by ver6 (kept for route_search compatibility)
    allowed_vehicle_types: Optional[list] = None  # set of vehicle types this service quotes
    carrier_role: Optional[str] = None  # "OWN_FLEET" (Hyundai Glovis) vs "PARTNER"
    source_dataset: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
