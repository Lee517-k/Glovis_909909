from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .glovis_bridge import list_nodes
from .progress import create_job, get_job
from .schemas import NegotiationRequest, NegotiationStartResponse, SaveRouteRequest
from .service import run_negotiation_job, save_route
from .store_bridge import get_store

router = APIRouter(prefix="/scenarios/yum", tags=["yum-scenario"])


@router.get("/nodes")
def get_nodes() -> dict[str, Any]:
    """출발지/도착지 드롭다운용 노드 목록 (ver6 데이터셋 기준)."""
    return {"nodes": list_nodes()}


@router.post("/negotiate", status_code=202, response_model=NegotiationStartResponse)
def start_negotiation(req: NegotiationRequest, bg: BackgroundTasks) -> NegotiationStartResponse:
    """경로 탐색 + 축별 규칙 기반 순위 산정을 백그라운드로 시작한다.
    (멀티에이전트 LLM 협상은 없음 — 그래서 즉시 끝나지만, 폴링 계약은
    참고 프로젝트와 동일하게 유지한다.)
    """
    request_id = f"YUM-{uuid.uuid4().hex[:12]}"
    create_job(request_id)
    bg.add_task(run_negotiation_job, request_id, req)
    return NegotiationStartResponse(request_id=request_id)


@router.get("/negotiate/{request_id}")
def get_negotiation(request_id: str) -> dict[str, Any]:
    job = get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail="request_id not found")
    return job


@router.post("/negotiate/{request_id}/save", status_code=201)
def save_negotiation_route(request_id: str, body: SaveRouteRequest) -> dict[str, Any]:
    """탐색 결과의 route 하나를 실제 시나리오로 SQLite에 저장한다."""
    job = get_job(request_id)
    if job is None:
        raise HTTPException(status_code=404, detail="request_id not found")
    if job["status"] != "COMPLETED" or not job.get("result"):
        raise HTTPException(status_code=409, detail="탐색이 아직 끝나지 않았습니다")

    try:
        return save_route(request_id, job["result"], body)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"route_id {body.route_id} 없음")


@router.get("/saved")
def list_saved(favorite: bool = False, status: str | None = None) -> dict[str, Any]:
    return {"scenarios": get_store().list(favorite_only=favorite, status=status)}


@router.get("/saved/{scenario_id}")
def get_saved(scenario_id: str) -> dict[str, Any]:
    sc = get_store().get(scenario_id)
    if sc is None:
        raise HTTPException(status_code=404, detail="scenario not found")
    return sc


@router.delete("/saved/{scenario_id}", status_code=204)
def delete_saved(scenario_id: str):
    if not get_store().delete(scenario_id):
        raise HTTPException(status_code=404, detail="scenario not found")


@router.patch("/saved/{scenario_id}/favorite")
def toggle_favorite(scenario_id: str) -> dict[str, Any]:
    """제안서 보관함 표시를 켜고 끈다. 시나리오 자체는 지우지 않는다."""
    store = get_store()
    if not store.exists(scenario_id):
        raise HTTPException(status_code=404, detail="scenario not found")
    store.toggle_favorite(scenario_id)
    return store.get(scenario_id)
