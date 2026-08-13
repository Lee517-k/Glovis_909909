"""CEU (Car Equivalent Unit) table — how much "space" each vehicle type
takes relative to a sedan, independent of weight. Sourced from
yum_ver2_all's own per-vehicle-class rows (data/yum_ver2_all/carrier_01_sea_glovis.json),
which already prices SEDAN/SUV/PICKUP/VAN/HIGH_HEAVY as distinct catalog rows.

EV is deliberately pinned to SEDAN (1.0), not given its own tier: an EV sedan
weighs ~300-400kg more than an ICE sedan but occupies the same deck footprint,
and CEU-based freight (both real RoRo pricing and this project's own datasets)
charges by space, not weight — pricing EV by weight would spike its rate for
no physical reason.
"""

CEU_TABLE = {
    "SEDAN": 1.0,
    "EV": 1.0,
    "SUV": 1.5,
    "PICKUP": 2.0,
    "LIGHT_COMMERCIAL": 2.6,  # mapped to yum_ver2_all's VAN tier
    "VAN": 2.6,
    "HIGH_HEAVY": 12.0,
}


def ceu_multiplier(vehicle_type):
    """cost_usd on a NormalizedService is always stored as the SEDAN-equivalent
    (CEU=1.0) baseline price. Multiply by this to get the actual quote for a
    specific requested vehicle_type."""
    return CEU_TABLE.get(vehicle_type, 1.0)
