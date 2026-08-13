"""Load the real negotiation agent without installing it as a package."""
from __future__ import annotations

import sys
from pathlib import Path

_SCREENING_DIR = Path(__file__).resolve().parents[4] / "llm-agent" / "screening"
if not _SCREENING_DIR.is_dir():
    raise RuntimeError(f"LLM agent directory not found: {_SCREENING_DIR}")
if str(_SCREENING_DIR) not in sys.path:
    sys.path.insert(0, str(_SCREENING_DIR))

from run_frontend_request import run_frontend_request  # noqa: E402

__all__ = ["run_frontend_request"]
