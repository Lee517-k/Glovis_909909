"""CEU (Car Equivalent Unit) table — how much "space" each vehicle type takes
relative to a sedan, independent of weight.

Ported as-is from the reference project's llm-agent/ceu.py.

EV is deliberately pinned to SEDAN (1.0), not given its own tier: an EV sedan
weighs more than an ICE sedan but occupies the same deck footprint, and
CEU-based freight charges by space, not weight.
"""
from __future__ import annotations

CEU_TABLE = {
    "SEDAN": 1.0,
    "EV": 1.0,
    "SUV": 1.5,
    "PICKUP": 2.0,
    "LIGHT_COMMERCIAL": 2.6,
    "VAN": 2.6,
    "HIGH_HEAVY": 12.0,
}


def ceu_multiplier(vehicle_type: str | None) -> float:
    """cost_usd on a NormalizedService is stored as the SEDAN-equivalent
    (CEU=1.0) baseline price. Multiply by this to get the actual quote for a
    specific requested vehicle_type."""
    return CEU_TABLE.get(vehicle_type, 1.0)
