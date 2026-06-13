"""Configuration for the Constitutional Court decisions pipeline."""

from core.config import (  # noqa: F401 - re-exported for package modules
    BACKOFF_BASE_SECONDS,
    BOT_AUTHOR,
    CACHE_ROOT,
    CONCURRENT_WORKERS,
    CONSTITUTIONAL_KR_REPO,
    LAW_API_BASE,
    LAW_API_KEY,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
    WORKSPACE_ROOT,
)

DETC_CACHE_DIR = CACHE_ROOT / "detc"
CONSTITUTIONAL_KR_DIR = CONSTITUTIONAL_KR_REPO

PANEL_CODE_MAP = {
    "430201": "전원재판부",
    "430202": "지정재판부",
}

BODY_SOURCES = frozenset({"api-text", "parsing-failed"})
