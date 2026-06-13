"""Tests for core/http.py."""

from unittest.mock import MagicMock

import pytest
import responses as responses_lib
from requests.exceptions import ConnectionError

from core.http import _redact_url_secrets, make_request
from core.throttle import Throttle

LAW_API_BASE = "http://www.law.go.kr/DRF"
TEST_URL = f"{LAW_API_BASE}/lawSearch.do"


def _throttle() -> Throttle:
    t = Throttle(delay_seconds=0)
    return t


def test_redact_url_secrets_masks_oc_parameter():
    text = "failed for /lawSearch.do?target=detc&OC=secret-key&display=100"

    redacted = _redact_url_secrets(text)

    assert "secret-key" not in redacted
    assert "OC=***" in redacted


@responses_lib.activate
def test_make_request_success():
    responses_lib.add(responses_lib.GET, TEST_URL, body=b"<ok/>", status=200)
    resp = make_request(TEST_URL, {"target": "law"}, throttle=_throttle(), api_key="testkey")
    assert resp.status_code == 200
    assert resp.content == b"<ok/>"


@responses_lib.activate
def test_make_request_adds_api_key():
    """OC parameter is injected automatically."""
    responses_lib.add(responses_lib.GET, TEST_URL, body=b"<ok/>", status=200)
    make_request(TEST_URL, {"target": "law"}, throttle=_throttle(), api_key="mykey")
    assert responses_lib.calls[0].request.url.count("OC=mykey") == 1


@responses_lib.activate
def test_make_request_retry_on_error():
    """On ConnectionError, retries up to max_retries."""
    responses_lib.add(responses_lib.GET, TEST_URL, body=ConnectionError("network down"))
    responses_lib.add(responses_lib.GET, TEST_URL, body=b"<ok/>", status=200)
    resp = make_request(
        TEST_URL, {}, throttle=_throttle(), api_key="k",
        max_retries=2, backoff_base=0.0
    )
    assert resp.status_code == 200
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_make_request_retry_on_429():
    """On 429, retries and eventually succeeds."""
    responses_lib.add(responses_lib.GET, TEST_URL, status=429)
    responses_lib.add(responses_lib.GET, TEST_URL, body=b"<ok/>", status=200)
    resp = make_request(
        TEST_URL, {}, throttle=_throttle(), api_key="k",
        max_retries=2, backoff_base=0.0
    )
    assert resp.status_code == 200
    assert len(responses_lib.calls) == 2


@responses_lib.activate
def test_make_request_exceeds_retries():
    """After exhausting retries, raises RuntimeError."""
    for _ in range(4):
        responses_lib.add(responses_lib.GET, TEST_URL, body=ConnectionError("fail"))
    with pytest.raises((RuntimeError, ConnectionError)):
        make_request(
            TEST_URL, {}, throttle=_throttle(), api_key="k",
            max_retries=2, backoff_base=0.0
        )
