"""Tests for constitutional/fetch_cache.py."""

import json
from pathlib import Path

import pytest

import constitutional.cache as detc_cache
import constitutional.fetch_cache as fetch_cache_mod
from core.counter import Counter


@pytest.fixture(autouse=True)
def patch_detc_cache_dir(tmp_path: Path, monkeypatch):
    detc_dir = tmp_path / "detc"
    detc_dir.mkdir(parents=True)
    monkeypatch.setattr(detc_cache, "CACHE_DIR", detc_dir)
    monkeypatch.setattr(fetch_cache_mod, "DETC_CACHE_DIR", detc_dir)
    monkeypatch.setattr(fetch_cache_mod, "_IDS_PATH", detc_dir / "detc_ids.json")


def _make_search_result(ids: list[str], total: int, page: int = 1) -> dict:
    return {
        "totalCnt": total,
        "page": page,
        "decisions": [{"헌재결정례일련번호": decision_id} for decision_id in ids],
    }


def test_fetch_all_ids_pages_and_saves_file(monkeypatch):
    calls = []

    def fake_search_decisions(**kwargs):
        calls.append(kwargs["page"])
        if kwargs["page"] == 1:
            return _make_search_result(["1", "2"], total=101, page=1)
        return _make_search_result(["2", "3"], total=101, page=2)

    monkeypatch.setattr(fetch_cache_mod, "search_decisions", fake_search_decisions)

    ids = fetch_cache_mod.fetch_all_ids(query="위헌", date_range="20240101~20241231")

    assert ids == ["1", "2", "3"]
    assert calls == [1, 2]
    data = json.loads(fetch_cache_mod._IDS_PATH.read_text(encoding="utf-8"))
    assert data["ids"] == ["1", "2", "3"]
    assert data["total"] == 3
    assert "collected_at" in data


def test_fetch_all_ids_limit_stops_pagination_early(monkeypatch):
    calls = []

    def fake_search_decisions(**kwargs):
        calls.append(kwargs["page"])
        page_ids = [str(i) for i in range(1, 101)]
        return _make_search_result(page_ids, total=1000, page=kwargs["page"])

    monkeypatch.setattr(fetch_cache_mod, "search_decisions", fake_search_decisions)

    ids = fetch_cache_mod.fetch_all_ids(limit=10)

    assert ids == [str(i) for i in range(1, 11)]
    assert calls == [1]
    data = json.loads(fetch_cache_mod._IDS_PATH.read_text(encoding="utf-8"))
    assert data["ids"] == ids


def test_fetch_all_ids_limit_zero_skips_api(monkeypatch):
    def fail_search_decisions(**_kwargs):
        raise AssertionError("search_decisions should not be called")

    monkeypatch.setattr(fetch_cache_mod, "search_decisions", fail_search_decisions)

    assert fetch_cache_mod.fetch_all_ids(limit=0) == []


def test_fetch_detail_task_skip_cached(monkeypatch):
    detc_cache.put_detail("123456", b"<detc/>")
    counter = Counter()
    called = False

    def fake_get_decision_detail(_decision_id):
        nonlocal called
        called = True

    monkeypatch.setattr(fetch_cache_mod, "get_decision_detail", fake_get_decision_detail)

    fetch_cache_mod._fetch_detail_task("123456", counter)

    assert called is False
    assert counter.snapshot() == (1, 0, 0)


def test_fetch_detail_task_fetches_new(monkeypatch):
    counter = Counter()
    fetched = []

    def fake_get_decision_detail(decision_id):
        fetched.append(decision_id)
        return b"<detc/>"

    monkeypatch.setattr(fetch_cache_mod, "get_decision_detail", fake_get_decision_detail)

    fetch_cache_mod._fetch_detail_task("999999", counter)

    assert fetched == ["999999"]
    assert counter.snapshot() == (0, 1, 0)


def test_fetch_detail_task_error_counted(monkeypatch):
    counter = Counter()

    def fake_get_decision_detail(_decision_id):
        raise RuntimeError("fail")

    monkeypatch.setattr(fetch_cache_mod, "get_decision_detail", fake_get_decision_detail)

    fetch_cache_mod._fetch_detail_task("bad_id", counter)

    assert counter.snapshot() == (0, 0, 1)
