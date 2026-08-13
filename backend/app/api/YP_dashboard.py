from fastapi import APIRouter

from app.repositories.YP_dashboard_repository import YPDashboardRepository

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
repository = YPDashboardRepository()


@router.get("")
def dashboard() -> dict[str, object]:
    return repository.summary()
