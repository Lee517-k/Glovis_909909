from __future__ import annotations

from app.domain.enums import CARBON_FACTOR_KG_CO2E_PER_TON_KM, CargoType, TransportMode
from app.domain.models import CargoInput
from app.planning.types import SegmentProposal

# Neither the sea nor the air datasets carry a distance field (only transit
# time), so a nominal service speed estimates distance for the carbon model.
# This is explicitly a synthetic estimate, not a real emissions calculation
# (see ASSUMPTIONS.md item 6 / TODO.md).
FALLBACK_SPEED_KMH = {
    TransportMode.SEA: 30.0,
    TransportMode.AIR: 800.0,
}

AVG_VEHICLE_WEIGHT_TON = 1.8


def cargo_weight_ton(cargo: CargoInput) -> float:
    if cargo.cargo_type == CargoType.FINISHED_VEHICLE:
        per_vehicle = cargo.vehicle.weight_kg_each / 1000 if cargo.vehicle else AVG_VEHICLE_WEIGHT_TON
        return cargo.quantity * per_vehicle
    return (cargo.weight_kg or 0) / 1000


def segment_distance_km(segment: SegmentProposal) -> float:
    if segment.distance_km:
        return segment.distance_km
    speed = FALLBACK_SPEED_KMH.get(segment.mode, 60.0)
    return speed * segment.transit_hours


def segment_co2_kg(segment: SegmentProposal, cargo: CargoInput) -> float:
    factor = CARBON_FACTOR_KG_CO2E_PER_TON_KM[segment.mode]
    return segment_distance_km(segment) * cargo_weight_ton(cargo) * factor


def grade_from_co2_per_ton(co2_kg: float, weight_ton: float) -> str:
    if weight_ton <= 0:
        return "C"
    per_ton = co2_kg / weight_ton
    if per_ton < 200:
        return "A"
    if per_ton < 500:
        return "B"
    if per_ton < 1000:
        return "C"
    if per_ton < 2000:
        return "D"
    return "E"
