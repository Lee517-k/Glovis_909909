"""나머지 화면용 API — 대시보드 알림 / 제안서 보관함 / 데이터 업로드 / 통합 검색.

GET    /api/search                     상단바 통합 검색
GET    /api/ops/alerts                 대시보드 알림 패널
POST   /api/ops/alerts/{id}/dismiss    알림 닫기
GET    /api/ops/overview               대시보드 상단 KPI + 알림 요약
GET    /api/proposals                  제안서 보관함 목록
POST   /api/proposals                  제안서 저장
DELETE /api/proposals/{id}             제안서 삭제
POST   /api/uploads                    운임표 업로드 → 컬럼 자동 매핑 + 검증
GET    /api/uploads/{batch_id}         업로드 배치 조회
POST   /api/uploads/{batch_id}/commit  검증 통과 시 반영
"""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.repositories import ops_repository as repo
from app.repositories import tracking_repository as tracking_repo
from app.repositories.dashboard_repository import get_dashboard_summary

router = APIRouter()


# ---------------------------------------------------------------------------
# 통합 검색
# ---------------------------------------------------------------------------
@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(8, ge=1, le=50)):
    return repo.global_search(q, limit)


# ---------------------------------------------------------------------------
# 대시보드
# ---------------------------------------------------------------------------
@router.get("/ops/alerts")
def ops_alerts():
    return repo.get_ops_alerts()


@router.post("/ops/alerts/{alert_id}/dismiss")
def dismiss_alert(alert_id: str):
    if not repo.dismiss_ops_alert(alert_id):
        raise HTTPException(status_code=404, detail="alert not found")
    return {"alert_id": alert_id, "dismissed": True}


@router.get("/ops/overview")
def ops_overview():
    """대시보드 상단 KPI(가용 자산은 기존 dashboard 집계 재사용) + 알림/추적 요약."""
    try:
        res = get_dashboard_summary()["resource_summary"]
    except Exception:  # Agent_Json 데이터셋이 없어도 추적/알림 부분은 살아 있어야 한다
        res = {"available_sea_services": 0, "available_rail_services": 0,
               "available_air_services": 0, "available_truck_services": 0}
    alerts = repo.get_ops_alerts()
    kpis = [
        {"icon": "ti-ship", "label": "가용 선박", "value": res["available_sea_services"], "unit": "척",
         "sub": "f계약 선대 서비스"},
        {"icon": "ti-train", "label": "가용 철도", "value": res["available_rail_services"], "unit": "슬롯",
         "sub": "f주간 운행 슬롯"},
        {"icon": "ti-plane", "label": "가용 항공", "value": res["available_air_services"], "unit": "편",
         "sub": "f오늘 출발 가능"},
        {"icon": "ti-truck", "label": "가용 트럭", "value": res["available_truck_services"], "unit": "대",
         "sub": "f권역 계약차량"},
        {"icon": "ti-alert-triangle", "label": "운항 리스크", "value": alerts["total"], "unit": "건",
         "sub": f"dCritical {alerts['counts'].get('critical', 0)} · Warning {alerts['counts'].get('warning', 0)}",
         "tone": "#D8443C"},
    ]
    return {
        "kpis": kpis,
        "alerts": alerts["alerts"],
        "tracking": tracking_repo.get_tracking_kpis(),
        "shipments": tracking_repo.search_shipments(scope="active", sort="eta", limit=5)["items"],
    }


# ---------------------------------------------------------------------------
# 제안서 보관함
# ---------------------------------------------------------------------------
class SavedProposalIn(BaseModel):
    proposal_id: str | None = None
    title: str
    cost_amount: float = 0
    currency: str = "KRW"
    days: float | None = None
    esg_grade: str | None = None
    tag_tone: str = "blue"
    tag_label: str = "승인 대기"
    modes: list[str] = Field(default_factory=list)


@router.get("/proposals")
def list_proposals():
    return repo.list_saved_proposals()


@router.post("/proposals", status_code=201)
def create_proposal(payload: SavedProposalIn):
    return repo.save_proposal(payload.model_dump())


@router.delete("/proposals/{proposal_id}")
def remove_proposal(proposal_id: str):
    if not repo.delete_proposal(proposal_id):
        raise HTTPException(status_code=404, detail="proposal not found")
    return {"proposal_id": proposal_id, "deleted": True}


# ---------------------------------------------------------------------------
# 데이터 업로드
# ---------------------------------------------------------------------------
@router.post("/uploads", status_code=201)
async def upload_rate_sheet(file: UploadFile = File(...)):
    """운임표 CSV를 받아 1) 컬럼 자동 매핑안 2) 검증 이슈 3) 예상 영향도를 만든다."""
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty file")
    return repo.analyze_upload(file.filename or "upload.csv", raw)


@router.get("/uploads/{batch_id}")
def get_upload(batch_id: str):
    batch = repo.get_upload_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return batch


@router.post("/uploads/{batch_id}/commit")
def commit_upload(batch_id: str):
    result = repo.commit_upload_batch(batch_id)
    if result is None:
        raise HTTPException(status_code=404, detail="batch not found")
    if not result["committed"]:
        raise HTTPException(status_code=409, detail=result["message"])
    return result
