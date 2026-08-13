"""메모리 기반 검색 작업(job) 저장소.

Ported from the reference project's backend/app/yum/progress.py. The stage
set is trimmed to what this backend actually emits — route_search and
ranking — since there is no per-leg negotiation (negotiate_leg,
scenario_negotiation) or scenario-selection step (scenarios_selected) left
to report on. The polling contract (create_job/get_job/complete_job/
fail_job/make_progress) is unchanged so the frontend's NegotiationConsole
works exactly as it does against the reference backend.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

JOBS: dict[str, dict[str, Any]] = {}
_LOCK = threading.Lock()

_STAGE_PCT = {
    "route_search": 10,
    "ranking": 80,
    "complete": 100,
}


def _pct(stage: str | None) -> int:
    return _STAGE_PCT.get(stage or "", 0)


def _describe(event: dict) -> str:
    stage, status = event.get("stage"), event.get("status")

    if stage == "route_search":
        if status == "start":
            return f"{event.get('origin')} → {event.get('destination')} 경로 탐색 중..."
        if status == "no_routes":
            return "경로를 찾지 못했습니다."
        if status == "deadline_infeasible":
            return f"납기 제약(최대 {event.get('max_transit_days')}일)을 만족하는 경로가 없습니다 — 후보 {event.get('n_candidates')}개 전부 기각"
        if status == "deadline_filtered":
            return f"납기 제약으로 {event.get('n_excluded')}개 기각, {event.get('n_remaining')}개 남음"
        return f"후보 경로 {event.get('n_routes_found')}개 발견"

    if stage == "ranking":
        return "축별 추천 순위 산정 중..." if status == "start" else "순위 산정 완료"

    if stage == "complete":
        return "탐색 완료, 결과 정리 중..."

    return f"{stage} {status or ''}".strip()


def create_job(request_id: str) -> None:
    with _LOCK:
        JOBS[request_id] = {
            "request_id": request_id,
            "status": "PROCESSING",
            "progress": 0,
            "stage": "queued",
            "message": "대기 중...",
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
            job["progress"] = _pct(event.get("stage"))
            job["message"] = message
            job["events"].append({**event, "message": message})

    return cb


def get_job(request_id: str) -> dict | None:
    with _LOCK:
        job = JOBS.get(request_id)
        return dict(job) if job is not None else None


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
