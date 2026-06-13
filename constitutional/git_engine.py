"""Git operations for committing Constitutional Court decision files."""

import logging
from pathlib import Path

from core.config import BOT_AUTHOR
from core.git_engine import commit_exists, commit_with_historical_date

from .converter import format_date, panel_name

logger = logging.getLogger(__name__)


def _commit_date(parsed: dict) -> str:
    date = format_date(parsed.get("종국일자", "")) or "1970-01-01"
    return date if date >= "1970-01-01" else "1970-01-01"


def build_commit_msg(parsed: dict) -> str:
    serial = str(parsed.get("헌재결정례일련번호", ""))
    case_name = parsed.get("사건명", "")
    case_no = parsed.get("사건번호", "")
    case_type = parsed.get("사건종류명", "") or "기타"
    panel = panel_name(parsed.get("재판부구분코드", ""))
    title = f"헌재결정례: {case_name}" if case_name else f"헌재결정례: {case_no}"
    return "\n".join([
        title,
        "",
        f"헌재결정례: https://www.law.go.kr/DRF/lawService.do?target=detc&ID={serial}",
        f"종국일자: {_commit_date(parsed)}",
        f"사건번호: {case_no}",
        f"사건종류: {case_type}",
        f"재판부: {panel}",
        f"헌재결정례일련번호: {serial}",
    ])


def commit_decision(
    repo_dir: Path,
    file_path: str,
    parsed: dict,
    *,
    skip_dedup: bool = False,
) -> bool:
    serial = str(parsed.get("헌재결정례일련번호", ""))
    key = f"헌재결정례일련번호: {serial}"
    if not skip_dedup and commit_exists(repo_dir, key):
        logger.debug("Commit exists for %s, skipping", key)
        return False
    return commit_with_historical_date(
        repo_dir,
        [Path(file_path)],
        build_commit_msg(parsed),
        _commit_date(parsed),
        author=BOT_AUTHOR,
        dedup_grep_key=None if skip_dedup else key,
    )
