from types import SimpleNamespace

import pytest

import constitutional.cache as ccache
from constitutional import api_client


def test_search_decisions_parses_list(monkeypatch):
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<LawSearch>
  <totalCnt>1</totalCnt>
  <page>1</page>
  <detc id="1">
    <헌재결정례일련번호>58386</헌재결정례일련번호>
    <종국일자>20240328</종국일자>
    <사건번호>2020헌마123</사건번호>
    <사건명>자동차관리법 제26조 등 위헌확인</사건명>
    <헌재결정례상세링크>/DRF/lawService.do?target=detc&amp;ID=58386</헌재결정례상세링크>
  </detc>
</LawSearch>
""".encode("utf-8")

    captured = {}

    def fake_request(url, params):
        captured.update(params)
        return SimpleNamespace(content=xml)

    monkeypatch.setattr(api_client, "_request", fake_request)

    result = api_client.search_decisions(date_range="20240101~20241231")

    assert captured["target"] == "detc"
    assert captured["edYd"] == "20240101~20241231"
    assert result["totalCnt"] == 1
    assert result["decisions"][0]["헌재결정례일련번호"] == "58386"


def test_get_decision_detail_fetches_and_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(ccache, "CACHE_DIR", tmp_path)
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<DetcService><헌재결정례일련번호>58386</헌재결정례일련번호></DetcService>
""".encode("utf-8")

    def fake_request(url, params):
        assert params["target"] == "detc"
        assert params["ID"] == "58386"
        return SimpleNamespace(content=xml)

    monkeypatch.setattr(api_client, "_request", fake_request)

    assert api_client.get_decision_detail("58386") == xml
    assert (tmp_path / "58386.xml").read_bytes() == xml


def test_get_decision_detail_rejects_non_decision_response(monkeypatch, tmp_path):
    monkeypatch.setattr(ccache, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        api_client,
        "_request",
        lambda _url, _params: SimpleNamespace(content=b"<Law>not found</Law>"),
    )

    with pytest.raises(RuntimeError, match="No Constitutional Court decision"):
        api_client.get_decision_detail("0")
