"""Normalized service record shared by every dataset adapter.

Every adapter (adapters.py) reads one candidate dataset's native format and
emits a list of NormalizedService objects in this shape. Nothing downstream
(route_search.py, screen.py) knows which of the 6 datasets it came from.
"""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NormalizedService:
    service_id: str
    carrier_id: str
    carrier_name: str
    mode: str  # sea | rail | road | air
    origin: str
    destination: str
    cost_usd: float               # all-in, USD, per shipment unit (vehicle/cbm/kg — see cost_unit)
    cost_unit: str                # "vehicle" | "cbm" | "kg" | "container" | "shipment"
    transit_days: float
    wait_days: float
    total_days: float             # transit_days + wait_days
    reliability_score: float
    co2_kg: Optional[float]
    available_capacity: Optional[float]
    cargo_ok: bool = True          # True unless the dataset says this leg can't carry the test cargo
    priority_level: str = "BALANCED"  # carrier's self-bias: LOW_COST/FASTEST/GREEN/BALANCED
    vehicle_class: Optional[str] = None          # yum_ver2_all: this row IS one specific vehicle class
    allowed_vehicle_types: Optional[list] = None  # ver5/yubin_ver4/v3: flat price covers this SET of types
    carrier_role: Optional[str] = None           # ver6: "OWN_FLEET" (Glovis) vs "PARTNER", straight from the data
    source_dataset: str = ""
    scenario_group: Optional[str] = None  # Set1/Set2/Set3 for v1_final/v2_fixed — legs from
                                           # different groups must never be chained together
    raw: dict[str, Any] = field(default_factory=dict)
