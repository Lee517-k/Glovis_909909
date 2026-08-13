from fastapi import APIRouter

from app.api import allocation, dashboard, nodes, ops, scenarios, tracking
from app.yum.router import router as yum_negotiation_router

api_router = APIRouter(prefix="/api")
api_router.include_router(nodes.router, tags=["nodes"])
api_router.include_router(scenarios.router, tags=["scenarios"])
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(yum_negotiation_router)
# 운송 추적 / 운송사 배분 (Control Tower 실행 화면)
api_router.include_router(tracking.router, tags=["tracking"])
api_router.include_router(allocation.router, tags=["allocation"])
# 대시보드 알림 · 제안서 보관함 · 데이터 업로드 · 통합 검색
api_router.include_router(ops.router, tags=["ops"])