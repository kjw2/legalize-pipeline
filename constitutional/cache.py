"""File-based cache for raw Constitutional Court decision XML responses."""

import os
from pathlib import Path

from core.atomic_io import atomic_write_bytes

from .config import DETC_CACHE_DIR

CACHE_DIR = Path(os.environ["LEGALIZE_DETC_CACHE_DIR"]) if os.environ.get("LEGALIZE_DETC_CACHE_DIR") else DETC_CACHE_DIR


def detail_path(decision_id: str) -> Path:
    return CACHE_DIR / f"{decision_id}.xml"


def get_detail(decision_id: str) -> bytes | None:
    path = detail_path(str(decision_id))
    return path.read_bytes() if path.exists() else None


def put_detail(decision_id: str, content: bytes) -> None:
    path = detail_path(str(decision_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, content)


def list_cached_ids() -> list[str]:
    if not CACHE_DIR.exists():
        return []
    return sorted(p.stem for p in CACHE_DIR.glob("*.xml"))
