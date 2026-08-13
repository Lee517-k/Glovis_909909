"""Shared database locations used by the control-tower backends."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "Data"
MERGED_DB_PATH = DATA_DIR / "glovis_merged.db"
