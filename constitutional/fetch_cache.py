"""Fetch and cache raw Constitutional Court decision detail API responses."""

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

from core.counter import Counter

from . import cache
from .api_client import get_decision_detail, search_decisions
from .config import CONCURRENT_WORKERS, DETC_CACHE_DIR

logger = logging.getLogger(__name__)

_IDS_PATH = DETC_CACHE_DIR / "detc_ids.json"
_KST = timezone(timedelta(hours=9))


def fetch_all_ids(*, query: str = "", date_range: str = "", limit: int | None = None) -> list[str]:
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")

    all_ids: list[str] = []
    seen: set[str] = set()
    page = 1
    while limit is None or len(all_ids) < limit:
        result = search_decisions(
            query=query,
            page=page,
            display=100,
            sort="efasc",
            date_range=date_range,
        )
        total = result["totalCnt"]
        for decision in result["decisions"]:
            decision_id = decision.get("헌재결정례일련번호", "")
            if decision_id and decision_id not in seen:
                seen.add(decision_id)
                all_ids.append(decision_id)
                if limit is not None and len(all_ids) >= limit:
                    break
        logger.info("detc search page %s: %s/%s", page, len(all_ids), total)
        if (limit is not None and len(all_ids) >= limit) or page * 100 >= total or not result["decisions"]:
            break
        page += 1

    DETC_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "collected_at": datetime.now(_KST).isoformat(),
        "total": len(all_ids),
        "ids": all_ids,
    }
    _IDS_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    logger.info("Saved %s IDs to %s", len(all_ids), _IDS_PATH)
    return all_ids


def _fetch_detail_task(decision_id: str, counter: Counter) -> None:
    if cache.get_detail(decision_id) is not None:
        counter.inc("cached")
        return
    try:
        get_decision_detail(decision_id)
        counter.inc("fetched")
    except Exception:
        logger.exception("Failed detc ID=%s", decision_id)
        counter.inc("errors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache Constitutional Court decisions")
    parser.add_argument("--limit", type=int, help="Limit number of decisions to fetch")
    parser.add_argument("--skip-list", action="store_true", help="Reuse detc_ids.json")
    parser.add_argument("--workers", type=int, default=CONCURRENT_WORKERS)
    parser.add_argument("--query", default="")
    parser.add_argument("--date-range", default="", help="종국일자 range YYYYMMDD~YYYYMMDD")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.skip_list:
        if not _IDS_PATH.exists():
            logger.error("detc_ids.json not found at %s", _IDS_PATH)
            raise SystemExit(1)
        all_ids = json.loads(_IDS_PATH.read_text(encoding="utf-8"))["ids"]
    else:
        all_ids = fetch_all_ids(query=args.query, date_range=args.date_range, limit=args.limit)

    if args.limit is not None:
        all_ids = all_ids[:args.limit]

    counter = Counter()
    done = 0
    total = len(all_ids)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_fetch_detail_task, decision_id, counter): decision_id for decision_id in all_ids}
        for future in as_completed(futures):
            future.result()
            done += 1
            if done % 500 == 0:
                snap = counter.snapshot_all()
                logger.info("Progress: %s/%s %s", done, total, snap)

    logger.info("Done: %s", counter.snapshot_all())


if __name__ == "__main__":
    main()
