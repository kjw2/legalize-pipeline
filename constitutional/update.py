"""Incremental Constitutional Court decision update."""

import argparse
import logging
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.atomic_io import atomic_write_text

from .api_client import get_decision_detail, search_decisions
from .config import CONSTITUTIONAL_KR_DIR
from .converter import (
    decision_to_markdown,
    get_decision_path,
    parse_decision_xml,
    reset_path_registry,
)
from .git_engine import commit_decision

logger = logging.getLogger(__name__)

_KST = timezone(timedelta(hours=9))
_SERIAL_RE = re.compile(r"^헌재결정례일련번호:\s*'?(?P<serial>\d+)'?\s*$")


def _date_range(days: int) -> str:
    end = datetime.now(_KST)
    start = end - timedelta(days=days)
    return f"{start:%Y%m%d}~{end:%Y%m%d}"


def _frontmatter_serial(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[:16]:
            match = _SERIAL_RE.match(line)
            if match:
                return match.group("serial")
    except OSError:
        return None
    return None


def _resolve_output_path(path: str, parsed: dict, output_dir: Path) -> str:
    existing_serial = _frontmatter_serial(output_dir / path)
    serial = str(parsed.get("헌재결정례일련번호", ""))
    if existing_serial is None or existing_serial == serial:
        return path
    base = Path(path)
    return str(base.with_name(f"{base.stem}_{serial}{base.suffix}"))


def _collect_recent(days: int) -> list[dict]:
    date_range = _date_range(days)
    logger.info("Searching detc in date range: %s", date_range)
    decisions: list[dict] = []
    seen: set[str] = set()
    page = 1
    while True:
        result = search_decisions(page=page, display=100, sort="efasc", date_range=date_range)
        total = result["totalCnt"]
        for decision in result["decisions"]:
            decision_id = decision.get("헌재결정례일련번호", "")
            if decision_id and decision_id not in seen:
                seen.add(decision_id)
                decisions.append(decision)
        logger.info("detc page %s: %s/%s", page, len(decisions), total)
        if page * 100 >= total or not result["decisions"]:
            break
        page += 1
    decisions.sort(key=lambda item: (item.get("종국일자", "") or "99999999", item.get("헌재결정례일련번호", "")))
    return decisions


def _committed_ids(repo: Path) -> set[str]:
    if not (repo / ".git").exists():
        return set()
    result = subprocess.run(
        ["git", "log", "--all", "--format=%B"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return set()
    prefix = "헌재결정례일련번호: "
    return {
        line[len(prefix):].strip()
        for line in result.stdout.splitlines()
        if line.startswith(prefix) and line[len(prefix):].strip()
    }


def run(
    *,
    days: int = 14,
    dry_run: bool = False,
    output_dir: Path = CONSTITUTIONAL_KR_DIR,
    commit: bool = False,
    refresh_recent: bool = False,
) -> dict[str, int]:
    reset_path_registry()
    recent = _collect_recent(days)
    committed_ids = _committed_ids(output_dir) if commit else set()
    candidates = [
        decision for decision in recent
        if decision.get("헌재결정례일련번호", "") not in committed_ids
    ]

    written = 0
    committed = 0
    errors = 0
    for i, decision in enumerate(candidates, 1):
        decision_id = decision["헌재결정례일련번호"]
        try:
            raw = get_decision_detail(decision_id, refresh=refresh_recent)
            parsed = parse_decision_xml(raw)
            if parsed is None:
                errors += 1
                continue
            path = _resolve_output_path(get_decision_path(parsed), parsed, output_dir)
            if dry_run:
                logger.info("[dry-run] Would write %s", path)
                continue
            target = output_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, decision_to_markdown(parsed))
            written += 1
            if commit and commit_decision(output_dir, path, parsed, skip_dedup=True):
                committed += 1
        except Exception:
            logger.exception("Failed detc ID=%s", decision_id)
            errors += 1
        if i % 50 == 0:
            logger.info("Progress: %s/%s written=%s committed=%s errors=%s", i, len(candidates), written, committed, errors)

    stats = {
        "found": len(recent),
        "candidates": len(candidates),
        "written": written,
        "committed": committed,
        "errors": errors,
    }
    logger.info("detc update done: %s", stats)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental Constitutional Court decision update")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=CONSTITUTIONAL_KR_DIR)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--refresh-recent", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    stats = run(
        days=args.days,
        dry_run=args.dry_run,
        output_dir=args.output_dir,
        commit=args.commit,
        refresh_recent=args.refresh_recent,
    )
    print(
        f"found={stats['found']} candidates={stats['candidates']} "
        f"written={stats['written']} committed={stats['committed']} errors={stats['errors']}"
    )


if __name__ == "__main__":
    main()
