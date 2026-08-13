from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.repositories.yp_data_repository import YPDataRepository


router = APIRouter(prefix="/yp", tags=["carrier-data"])
repository = YPDataRepository()


class ValidationAction(BaseModel):
    capability_id: str
    status: str


class ValidationActionBatch(BaseModel):
    carrier_id: str
    actions: list[ValidationAction]


@router.get("/capabilities/summary")
def capability_summary() -> dict[str, object]:
    return repository.summary()


@router.get("/capabilities")
def capabilities(
    limit: int = Query(default=1000, ge=1, le=5000),
    mode: str | None = Query(default=None),
    approval_status: str = Query(default="approved"),
) -> dict[str, object]:
    if mode not in {None, "sea", "air", "rail", "road"}:
        raise HTTPException(status_code=400, detail="Invalid transport mode")
    if approval_status not in {"approved", "unapproved", "all"}:
        raise HTTPException(status_code=400, detail="Invalid approval status")
    return {"items": repository.capabilities(limit=limit, mode=mode, approval_status=approval_status)}


@router.get("/reliability")
def reliability() -> dict[str, object]:
    return {"items": repository.reliability()}


@router.get("/reliability/{carrier_id}")
def reliability_detail(carrier_id: str) -> dict[str, object]:
    result = repository.reliability_detail(carrier_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Carrier not found")
    return result


@router.post("/reliability/actions")
def save_reliability_actions(payload: ValidationActionBatch) -> dict[str, int]:
    allowed = {"unverified", "correction_candidate", "awaiting_carrier_response", "verified", "excluded"}
    if any(action.status not in allowed for action in payload.actions):
        raise HTTPException(status_code=400, detail="Invalid validation status")
    updated = repository.update_validation_actions(payload.carrier_id, [(action.capability_id, action.status) for action in payload.actions])
    return {"updated": updated}
