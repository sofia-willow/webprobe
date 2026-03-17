"""Tests for webprobe data models."""

import datetime as dt

from webprobe.models import ProbeResult, RedirectHop


def test_healthy_result():
    r = ProbeResult(url="https://example.com", status_code=200, response_time_ms=150.0)
    assert r.is_healthy is True
    assert r.ssl_warning is False


def test_unhealthy_result():
    r = ProbeResult(url="https://example.com", status_code=500, response_time_ms=500.0)
    assert r.is_healthy is False


def test_error_result():
    r = ProbeResult(url="https://bad.example", error="Connection refused")
    assert r.is_healthy is False
    assert r.status_code is None


def test_ssl_warning():
    r = ProbeResult(
        url="https://example.com",
        status_code=200,
        ssl_days_remaining=10,
    )
    assert r.ssl_warning is True


def test_ssl_ok():
    r = ProbeResult(
        url="https://example.com",
        status_code=200,
        ssl_days_remaining=90,
    )
    assert r.ssl_warning is False


def test_to_dict():
    r = ProbeResult(url="https://example.com", status_code=200, response_time_ms=100.5)
    d = r.to_dict()
    assert d["url"] == "https://example.com"
    assert d["status_code"] == 200
    assert d["response_time_ms"] == 100.5
    assert d["healthy"] is True


def test_redirect_chain():
    r = ProbeResult(
        url="http://example.com",
        status_code=200,
        redirect_chain=[RedirectHop(url="http://example.com", status_code=301)],
        final_url="https://example.com",
    )
    assert len(r.redirect_chain) == 1
    assert r.final_url == "https://example.com"
    assert r.is_healthy is True
