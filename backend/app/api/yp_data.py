from fastapi import APIRouter, HTTPException, Query

from app.repositories.yp_data_repository import YPDataRepository


router = APIRouter(prefix="/yp", tags=["carrier-data"])
repository = YPDataRepository()


@router.get("/capabilities/summary")
def capability_summary() -> dict[str, object]:
    return repository.summary()


@router.get("/capabilities")
def capabilities(
    limit: int = Query(default=100, ge=1, le=1000),
    mode: str | None = Query(default=None),
) -> dict[str, object]:
    if mode not in {None, "sea", "air", "rail", "road"}:
        raise HTTPException(status_code=400, detail="Invalid transport mode")
    return {"items": repository.capabilities(limit=limit, mode=mode)}


@router.get("/reliability")
def reliability() -> dict[str, object]:
    return {"items": repository.reliability()}

