"""Pydantic request models for the scenario search / save API.

Mirrors the reference project's backend/app/yum/schemas.py field-for-field
(NegotiationRequest/NegotiationStartResponse/SaveRouteRequest), minus the
docstring notes about LLM negotiation timing since this backend has no LLM
step to wait on.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

CargoType = Literal["SEDAN", "SUV", "EV", "PICKUP", "LIGHT_COMMERCIAL", "HIGH_HEAVY"]
Axis = Literal["COST", "TIME", "CO2", "RELIABILITY", "BALANCED"]


class NegotiationRequest(BaseModel):
    origin: str
    destination: str
    vehicle_type: CargoType = "SEDAN"
    quantity: int = Field(gt=0)
    selected_axis: Axis = "BALANCED"
    top_k: int = Field(default=3, ge=1, le=10)
    max_transit_days: Optional[float] = Field(default=None, gt=0)


class NegotiationStartResponse(BaseModel):
    request_id: str
    status: Literal["PROCESSING"] = "PROCESSING"


class SaveRouteRequest(BaseModel):
    route_id: str
    etd: Optional[datetime] = None
    scenario_name: Optional[str] = None
    is_favorite: bool = False
