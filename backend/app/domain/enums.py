from enum import StrEnum


class CargoType(StrEnum):
    FINISHED_VEHICLE = "FINISHED_VEHICLE"
    AUTO_PARTS = "AUTO_PARTS"
    GENERAL = "GENERAL"


class TransportMode(StrEnum):
    SEA = "sea"
    RAIL = "rail"
    TRUCK = "truck"
    AIR = "air"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ScenarioStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# Section 9.2 of the spec, restricted to the 4 weights the frontend-first
# doc's scenario contract actually exposes (cost/time/reliability/risk).
DEFAULT_PRIORITY_WEIGHTS = {
    "cost": 0.30,
    "time": 0.25,
    "reliability": 0.25,
    "risk": 0.20,
}

CARBON_FACTOR_KG_CO2E_PER_TON_KM = {
    TransportMode.SEA: 0.015,
    TransportMode.RAIL: 0.025,
    TransportMode.TRUCK: 0.090,
    TransportMode.AIR: 0.600,
}

# No dataset field gives inter-facility transfer time between co-located
# facilities that are not ports (e.g. a rail terminal and a vehicle yard in
# the same city). Ports carry their own processing hours; this constant only
# covers the non-port case. See ASSUMPTIONS.md item 5.
DEFAULT_COLOCATED_TRANSFER_HOURS = 4.0
