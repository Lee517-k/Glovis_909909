"""Node listing for the origin/destination dropdowns.

Mirrors the reference project's backend/app/yum/glovis_bridge.py — there
`ensure_loaded()`/`list_nodes()` lazily loaded the ver6 dataset into a
shared `glovis_scenario.engine` module. This project's dataset loading
already lives in app.dataset.loader (lazy + cached there), so this module
is just a thin pass-through kept for structural parity with the reference's
app/yum package.
"""
from __future__ import annotations

from typing import Any

from app.dataset import loader


def list_nodes() -> list[dict[str, Any]]:
    return loader.get_nodes()
