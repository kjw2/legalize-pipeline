"""Thin wrapper around law.go.kr OpenAPI for Constitutional Court decisions."""

import logging
from xml.etree import ElementTree

import requests

from core.http import make_request
from core.throttle import Throttle

from . import cache
from .config import (
    BACKOFF_BASE_SECONDS,
    LAW_API_BASE,
    LAW_API_KEY,
    MAX_RETRIES,
    REQUEST_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

_throttle = Throttle(REQUEST_DELAY_SECONDS)


def _request(url: str, params: dict) -> requests.Response:
    return make_request(
        url,
        params,
        throttle=_throttle,
        api_key=LAW_API_KEY,
        max_retries=MAX_RETRIES,
        backoff_base=BACKOFF_BASE_SECONDS,
    )


def _require_no_api_error(root: ElementTree.Element, context: str) -> None:
    result = root.findtext("result")
    if result and "실패" in result:
        raise RuntimeError(f"API error ({context}): {result} - {root.findtext('msg', '')}")


def _items(root: ElementTree.Element) -> list[ElementTree.Element]:
    items = root.findall(".//detc")
    if items:
        return items
    return [item for item in root.iter() if item.findtext("헌재결정례일련번호") is not None]


def search_decisions(
    query: str = "",
    page: int = 1,
    display: int = 100,
    sort: str = "efasc",
    search: str = "",
    date: str = "",
    date_range: str = "",
    case_no: str = "",
) -> dict:
    """Search Constitutional Court decisions via ``target=detc``.

    Returns ``{"totalCnt": int, "page": int, "decisions": list[dict]}``.
    """
    params = {
        "target": "detc",
        "type": "XML",
        "query": query,
        "page": str(page),
        "display": str(display),
        "sort": sort,
    }
    if search:
        params["search"] = str(search)
    if date:
        params["date"] = str(date)
    if date_range:
        params["edYd"] = str(date_range)
    if case_no:
        params["nb"] = str(case_no)

    resp = _request(f"{LAW_API_BASE}/lawSearch.do", params)
    root = ElementTree.fromstring(resp.content)
    _require_no_api_error(root, f"detc search page {page}")

    decisions = []
    for item in _items(root):
        decisions.append({
            "헌재결정례일련번호": item.findtext("헌재결정례일련번호", ""),
            "종국일자": item.findtext("종국일자", ""),
            "사건번호": item.findtext("사건번호", ""),
            "사건명": item.findtext("사건명", ""),
            "헌재결정례상세링크": (
                item.findtext("헌재결정례상세링크", "")
                or item.findtext("상세링크", "")
            ),
        })

    return {
        "totalCnt": int(root.findtext("totalCnt", "0") or 0),
        "page": int(root.findtext("page", str(page)) or page),
        "decisions": decisions,
    }


def get_decision_detail(decision_id: str | int, *, refresh: bool = False) -> bytes:
    """Fetch raw Constitutional Court decision XML by 헌재결정례일련번호."""
    decision_id = str(decision_id)
    cached = cache.get_detail(decision_id)
    if cached and not refresh:
        logger.debug("Cache hit: detc detail ID=%s", decision_id)
        return cached

    resp = _request(f"{LAW_API_BASE}/lawService.do", {
        "target": "detc",
        "ID": decision_id,
        "type": "XML",
    })
    raw = resp.content
    root = ElementTree.fromstring(raw)
    _require_no_api_error(root, f"detc detail ID={decision_id}")
    if root.findtext(".//헌재결정례일련번호") is None:
        message = (root.text or "").strip() or f"unexpected root <{root.tag}>"
        raise RuntimeError(f"No Constitutional Court decision for ID {decision_id}: {message}")
    cache.put_detail(decision_id, raw)
    return raw
