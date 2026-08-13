"""'운송사 배분' 메뉴 API.

GET /api/allocation/regions        지역권 탭 목록
GET /api/allocation/hubs           거점별 물량(지도 버블 + 범례)
GET /api/allocation/allocations    지역권 × 운송사 배분 + HHI 집중도
GET /api/allocation/carriers       운송사 현황 표
GET /api/allocation/carriers.csv   운송사 현황 CSV 내보내기
GET /api/allocation/summary        배분 요약(평균 HHI, 위험 지역권)
GET /api/allocation/overview       위 항목을 한 번에(탭 전환 시 1회 호출)
"""

from fastapi import APIRouter, Query, Response

from app.repositories import allocation_repository as repo

router = APIRouter(prefix="/allocation")


@router.get("/regions")
def regions():
    return repo.get_regions()


@router.get("/hubs")
def hubs(region_id: str | None = Query(None, description="지역권 필터. 미지정 시 전체")):
    return repo.get_hub_volumes(region_id)


@router.get("/allocations")
def allocations(region_id: str | None = None):
    """지역권별 운송사 점유율과 HHI(허핀달 집중도)를 계산해 반환한다."""
    return repo.get_allocations(region_id)


@router.get("/carriers")
def carriers(
    region_id: str | None = None,
    mode: str | None = Query(None, description="모드 필터(CSV). 예: sea,rail"),
    sort: str = Query("-share", description="-share | share | -ot | ot | -volume | volume | name"),
):
    return repo.get_carriers(region_id, mode, sort)


@router.get("/carriers.csv")
def carriers_csv(region_id: str | None = None, mode: str | None = None):
    """화면의 'CSV' 버튼용. Excel 한글 대응으로 UTF-8 BOM을 붙여 내려준다."""
    body = repo.carriers_csv(region_id, mode)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="carriers.csv"'},
    )


@router.get("/summary")
def summary(region_id: str | None = None):
    return repo.get_allocation_summary(region_id)


@router.get("/overview")
def overview(region_id: str | None = None):
    return {
        "regions": repo.get_regions(),
        "hubs": repo.get_hub_volumes(region_id),
        "allocations": repo.get_allocations(region_id),
        "carriers": repo.get_carriers(region_id),
        "summary": repo.get_allocation_summary(region_id),
    }
