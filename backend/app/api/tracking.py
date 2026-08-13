"""'운송 추적' 메뉴 API.

GET  /api/tracking/kpis                        상단 KPI 5종
GET  /api/tracking/shipments                   화물 목록(검색·필터·정렬·페이징)
GET  /api/tracking/shipments/{id}              화물 상세(요약 카드 + AI 알림)
GET  /api/tracking/shipments/{id}/segments     구간 진행(계획 대비 실적) + 여정 타임라인
GET  /api/tracking/shipments/{id}/route        지도용 경로 지오메트리
GET  /api/tracking/shipments/{id}/overview     위 3개를 한 번에(초기 렌더 왕복 감소)
POST /api/tracking/alerts/{alert_id}/resolve   AI 알림 조치 완료
"""

from fastapi import APIRouter, HTTPException, Query

from app.repositories import HS_tracking_repository as repo

router = APIRouter(prefix="/tracking")


@router.get("/kpis")
def tracking_kpis():
    return repo.get_tracking_kpis()


@router.get("/shipments")
def list_shipments(
    q: str | None = Query(None, description="운송번호·화물명·출발지/도착지·현재위치·운송사 검색어"),
    status: str | None = Query(None, description="상태 필터(CSV). 예: DELAYED,CUSTOMS_HOLD"),
    mode: str | None = Query(None, description="운송 모드 필터(CSV). 예: sea,rail"),
    region_id: str | None = Query(None, description="지역권 필터"),
    eta_from: str | None = Query(None, description="예상 도착 시작일(YYYY-MM-DD)"),
    eta_to: str | None = Query(None, description="예상 도착 종료일(YYYY-MM-DD)"),
    scope: str = Query("active", pattern="^(active|all|completed|planned)$"),
    sort: str = Query("eta", description="eta | -eta | progress | -progress | risk | -risk | id | -id | name | -name"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """화면 검색창 · 필터 · 'ETA 순' 정렬 버튼이 모두 이 엔드포인트를 쓴다."""
    return repo.search_shipments(
        q=q, status=status, mode=mode, region_id=region_id,
        eta_from=eta_from, eta_to=eta_to,
        scope=scope, sort=sort, limit=limit, offset=offset,
    )


@router.get("/shipments/{shipment_id}")
def get_shipment(shipment_id: str):
    detail = repo.get_shipment_detail(shipment_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="shipment not found")
    return detail


@router.get("/shipments/{shipment_id}/segments")
def get_segments(shipment_id: str):
    data = repo.get_shipment_segments(shipment_id)
    if data is None:
        raise HTTPException(status_code=404, detail="shipment not found")
    return data


@router.get("/shipments/{shipment_id}/route")
def get_route(shipment_id: str):
    data = repo.get_shipment_route(shipment_id)
    if data is None:
        raise HTTPException(status_code=404, detail="shipment not found")
    return data


@router.get("/shipments/{shipment_id}/overview")
def get_overview(shipment_id: str):
    """상세 화면 진입 시 필요한 상세·구간·경로를 한 번에 내려준다."""
    detail = repo.get_shipment_detail(shipment_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="shipment not found")
    return {
        "detail": detail,
        "segments": repo.get_shipment_segments(shipment_id),
        "route": repo.get_shipment_route(shipment_id),
    }


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    if not repo.resolve_alert(alert_id):
        raise HTTPException(status_code=404, detail="alert not found")
    return {"alert_id": alert_id, "resolved": True, "kpis": repo.get_tracking_kpis()}
