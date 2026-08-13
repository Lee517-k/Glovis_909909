"""저장된 시나리오 SQLite 스토어에 대한 얇은 접근 계층.

Mirrors the reference project's backend/app/yum/store_bridge.py. The store
implementation itself (app.scenario.store.ScenarioStore) is a straight port
of the reference's glovis_scenario.ScenarioStore, pointed at this project's
Data/glovis_merged.db.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from app.scenario.store import ScenarioStore

_store: Optional[ScenarioStore] = None


def get_store() -> ScenarioStore:
    global _store
    if _store is None:
        _store = ScenarioStore(str(settings.merged_db_path))
        _store.init()
    return _store


def find_by_source(store: ScenarioStore, request_id: str, route_id: str) -> Optional[str]:
    """이 (검색 request_id, route_id) 조합으로 이미 저장된 시나리오가 있으면
    그 scenario_id를 돌려준다 — 같은 경로를 다시 저장(북마크→선택 등)해도
    새 행을 만들지 않고 기존 행을 덮어쓰기 위함."""
    for sc in store.list(tracking=False):
        if sc.get("source_request_id") == request_id and sc.get("source_route_id") == route_id:
            return sc["scenario_id"]
    return None
