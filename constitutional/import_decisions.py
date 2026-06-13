"""Import cached Constitutional Court decision XML files to Markdown."""

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from core.atomic_io import atomic_write_text
from core.counter import Counter

from .config import CONCURRENT_WORKERS, CONSTITUTIONAL_KR_DIR, DETC_CACHE_DIR
from .converter import (
    decision_to_markdown,
    get_decision_path,
    parse_decision_xml,
    reset_path_registry,
)
from .git_engine import commit_decision

logger = logging.getLogger(__name__)


def _sort_key(entry: tuple[dict, str]) -> tuple[str, int]:
    parsed, _path = entry
    serial = str(parsed.get("헌재결정례일련번호", ""))
    try:
        serial_key = int(serial)
    except ValueError:
        serial_key = 2**63 - 1
    return parsed.get("종국일자", "") or "99999999", serial_key


def _write_task(parsed: dict, path: str, output_dir: Path, dry_run: bool, counter: Counter) -> None:
    try:
        markdown = decision_to_markdown(parsed)
        if not dry_run:
            target = output_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(target, markdown)
        counter.inc("fetched")
    except Exception:
        logger.exception("Failed writing %s", path)
        counter.inc("errors")


def run(
    *,
    limit: int | None = None,
    dry_run: bool = False,
    workers: int = CONCURRENT_WORKERS,
    output_dir: Path = CONSTITUTIONAL_KR_DIR,
    git: bool = False,
    skip_dedup: bool = False,
) -> dict[str, int]:
    reset_path_registry()
    xml_files = sorted(p for p in DETC_CACHE_DIR.glob("*.xml") if p.suffix == ".xml")
    if limit is not None:
        xml_files = xml_files[:limit]

    entries: list[tuple[dict, str]] = []
    parse_errors = 0
    skipped_empty = 0
    for i, xml_file in enumerate(xml_files, 1):
        try:
            parsed = parse_decision_xml(xml_file.read_bytes())
            if parsed is None:
                parse_errors += 1
                continue
            if not parsed.get("헌재결정례일련번호"):
                skipped_empty += 1
                continue
            entries.append((parsed, get_decision_path(parsed)))
        except Exception:
            logger.exception("Failed parsing %s", xml_file)
            parse_errors += 1
        if i % 1000 == 0:
            logger.info("Parse progress: %s/%s", i, len(xml_files))

    counter = Counter()
    if git:
        for i, (parsed, path) in enumerate(sorted(entries, key=_sort_key), 1):
            if dry_run:
                counter.inc("fetched")
            else:
                try:
                    target = output_dir / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    atomic_write_text(target, decision_to_markdown(parsed))
                    if commit_decision(output_dir, path, parsed, skip_dedup=skip_dedup):
                        counter.inc("fetched")
                except Exception:
                    logger.exception("Failed importing %s", path)
                    counter.inc("errors")
            if i % 500 == 0:
                logger.info("Git progress: %s/%s", i, len(entries))
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(_write_task, parsed, path, output_dir, dry_run, counter)
                for parsed, path in entries
            ]
            for i, future in enumerate(as_completed(futures), 1):
                future.result()
                if i % 1000 == 0:
                    logger.info("Write progress: %s/%s", i, len(entries))

    snap = counter.snapshot_all()
    return {
        "total": len(xml_files),
        "converted": snap.get("fetched", 0),
        "skipped_empty": skipped_empty,
        "skipped_errors": parse_errors + snap.get("errors", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import cached Constitutional Court decisions")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=CONCURRENT_WORKERS)
    parser.add_argument("--output-dir", type=Path, default=CONSTITUTIONAL_KR_DIR)
    parser.add_argument("--git", action="store_true")
    parser.add_argument("--skip-dedup", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = run(
        limit=args.limit,
        dry_run=args.dry_run,
        workers=args.workers,
        output_dir=args.output_dir,
        git=args.git,
        skip_dedup=args.skip_dedup,
    )
    print(
        f"total={stats['total']} converted={stats['converted']} "
        f"skipped_errors={stats['skipped_errors']} skipped_empty={stats['skipped_empty']}"
    )


if __name__ == "__main__":
    main()
