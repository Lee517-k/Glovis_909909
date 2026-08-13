"""In-memory progress store for asynchronous multimodal-agent jobs."""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

_STAGE_PCT = {
    "loading_data": 3,
    "route_search": 5,
    "scenarios_selected": 15,
    "scenario_negotiation": 20,
    "negotiate_leg": 50,
    "ranking": 90,
    "complete": 100,
}


def _pct(event: dict) -> int:
    stage = event.get("stage")
    base = _STAGE_PCT.get(stage, 0)
    if stage == "scenario_negotiation":
        index, total = event.get("scenario_index"), event.get("of")
        if isinstance(index, int) and isinstance(total, int) and total > 0:
            return min(45, 20 + round(index / total * 25))
    if stage == "negotiate_leg":
        status_offset = {"round1_start": 0, "round1_done": 8, "round2_start": 15, "round2_done": 22, "done": 28}
        return min(88, base + status_offset.get(event.get("status"), 0))
    return base


def _describe(event: dict) -> str:
    stage, status = event.get("stage"), event.get("status")
    if stage == "loading_data":
        return "운송사 서비스와 노드 데이터를 불러오는 중입니다."
    if stage == "route_search":
        if status == "start":
            return f"{event.get('origin')} → {event.get('destination')} 운송 가능 경로를 탐색하는 중입니다."
        if status == "no_routes":
            return "조건에 맞는 운송 경로를 찾지 못했습니다."
        return f"후보 운송 경로 {event.get('n_routes_found', 0)}개를 찾았습니다."
    if stage == "scenarios_selected":
        return f"협상할 운송 시나리오 {event.get('count', 0)}개를 선정했습니다."
    if stage == "scenario_negotiation":
        index = event.get("scenario_index")
        display_index = index + 1 if isinstance(index, int) else index
        if status == "start":
            return f"시나리오 {display_index}/{event.get('of')} 멀티에이전트 협상을 시작합니다: {event.get('path')}"
        return f"시나리오 {display_index} 협상을 완료했습니다."
    if stage == "negotiate_leg":
        carrier = event.get("carrier_id") or "운송사"
        service = event.get("service_id") or "서비스"
        reason = event.get("reason")
        if status == "round1_start":
            return f"[{carrier}] {service} 1차 운송 조건을 요청하는 중입니다."
        if status == "round1_done":
            return f"[{carrier}] 1차 응답: {event.get('decision')}{f' · {reason}' if reason else ''}"
        if status == "round2_start":
            return f"[{carrier}] 제안 조건을 검토하고 재협상하는 중입니다."
        if status == "round2_done":
            return f"[{carrier}] 2차 협상 판단: {event.get('decision')}{f' · {reason}' if reason else ''}"
        if status == "self_operated":
            return f"[{carrier}] {service} 자사 운송 구간으로 바로 배차합니다."
        if status == "done":
            if event.get("deal_reached"):
                price = event.get("price_usd")
                return f"[{carrier}] 구간 협상 타결{f' · 대당 ${price}' if price is not None else ''}"
            return f"[{carrier}] 구간 협상 결렬{f' · {reason}' if reason else ''}"
    if stage == "ranking":
        return "비용·시간·탄소·신뢰도 기준으로 최종 순위를 계산하는 중입니다." if status == "start" else "추천 경로 순위 산정을 완료했습니다."
    if stage == "complete":
        return "멀티에이전트 탐색을 완료하고 결과를 정리하고 있습니다."
    return f"{stage or 'queued'} {status or ''}".strip()


def create_job(request_id: str) -> None:
    with _LOCK:
        JOBS[request_id] = {
            "request_id": request_id,
            "status": "PROCESSING",
            "progress": 0,
            "stage": "queued",
            "message": "멀티에이전트 실행을 준비하고 있습니다.",
            "events": [],
            "result": None,
            "error": None,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }


def make_progress(request_id: str):
    def cb(event: dict) -> None:
        message = _describe(event)
        with _LOCK:
            job = JOBS.get(request_id)
            if job is None:
                return
            job["stage"] = event.get("stage")
            job["progress"] = max(job["progress"], _pct(event))
            job["message"] = message
            job["events"].append({**event, "message": message})
    return cb


def get_job(request_id: str) -> dict | None:
    with _LOCK:
        job = JOBS.get(request_id)
        if job is None:
            return None
        return {**job, "events": list(job["events"])}


def complete_job(request_id: str, result: dict) -> None:
    with _LOCK:
        job = JOBS.get(request_id)
        if job is None:
            return
        job["status"] = "COMPLETED"
        job["progress"] = 100
        job["message"] = "완료"
        job["result"] = result


def fail_job(request_id: str, error: str) -> None:
    with _LOCK:
        job = JOBS.get(request_id)
        if job is None:
            return
        job["status"] = "FAILED"
        job["message"] = "실패"
        job["error"] = error
