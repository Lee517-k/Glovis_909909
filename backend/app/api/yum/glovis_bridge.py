"""Node listing for the origin/destination dropdowns.

Mirrors the reference project's backend/app/yum/glovis_bridge.py — there
`ensure_loaded()`/`list_nodes()` lazily loaded the ver6 dataset into a
shared `glovis_scenario.engine` module. This project's ver6 dataset loading
lives in app.dataset.yum_loader (lazy + cached there) — named yum_loader
because app.dataset.loader is a separate, unrelated dataset loader (a
different in-progress "System A"-style route planner, see
backend/app/planning/segment_route_search.py) that happened to want the
same module path. This module is just a thin pass-through kept for
structural parity with the reference's app/yum package.
"""
from __future__ import annotations

from typing import Any

from app.dataset import yum_loader as loader


def list_nodes() -> list[dict[str, Any]]:
    return loader.get_nodes()
