"""Tests for webprobe core functionality."""

from __future__ import annotations

import datetime as dt
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from webprobe.checker import probe_many, probe_url
from webprobe.cli import main, _normalise_url
from webprobe.models import ProbeResult, RedirectHop
from webprobe.output import render_csv, render_json


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestProbeResult:
    """Tests for the ProbeResult dataclass."""

    def test_healthy_2xx(self) -> None:
        r = ProbeResult(url="https://example.com", status_code=200)
        assert r.is_healthy is True

    def test_healthy_3xx(self) -> None:
        r = ProbeResult(url="https://example.com", status_code=301)
        assert r.is_healthy is True

    def test_unhealthy_4xx(self) -> None:
        r = ProbeResult(url="https://example.com", status_code=404)
        assert r.is_healthy is False

    def test_unhealthy_error(self) -> None:
        r = ProbeResult(url="https://example.com", error="Timeout")
        assert r.is_healthy is False

    def test_ssl_warning_true(self) -> None:
        r = ProbeResult(url="https://example.com", ssl_days_remaining=10)
        assert r.ssl_warning is True

    def test_ssl_warning_false(self) -> None:
        r = ProbeResult(url="https://example.com", ssl_days_remaining=90)
        assert r.ssl_warning is False

    def test_ssl_warning_none(self) -> None:
        r = ProbeResult(url="https://example.com")
        assert r.ssl_warning is False

    def test_to_dict(self) -> None:
        r = ProbeResult(
            url="https://example.com",
            status_code=200,
            response_time_ms=123.456,
            redirect_chain=[RedirectHop(url="http://example.com", status_code=301)],
            final_url="https://example.com",
        )
        d = r.to_dict()
        assert d["url"] == "https://example.com"
        assert d["status_code"] == 200
        assert d["response_time_ms"] == 123.46
        assert d["healthy"] is True
        assert len(d["redirect_chain"]) == 1
        assert d["redirect_chain"][0]["status_code"] == 301


class TestRedirectHop:
    def test_frozen(self) -> None:
        hop = RedirectHop(url="http://a.com", status_code=301)
        with pytest.raises(AttributeError):
            hop.url = "http://b.com"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Checker tests (mocked HTTP)
# ---------------------------------------------------------------------------

def _make_mock_response(
    status: int = 200,
    url: str = "https://example.com",
    history: list | None = None,
    content_length: int | None = 1234,
) -> MagicMock:
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.url = url
    resp.history = history or []
    resp.content_length = content_length
    resp.connection = None  # no SSL info in mock
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


class TestProbeUrl:
    @pytest.mark.asyncio
    async def test_successful_probe(self) -> None:
        mock_resp = _make_mock_response(200)
        session = MagicMock()
        session.get = MagicMock(return_value=mock_resp)

        result = await probe_url("https://example.com", session=session)

        assert result.status_code == 200
        assert result.error is None
        assert result.response_time_ms is not None
        assert result.is_healthy is True

    @pytest.mark.asyncio
    async def test_timeout_error(self) -> None:
        import asyncio

        session = MagicMock()
        session.get = MagicMock(side_effect=asyncio.TimeoutError())

        result = await probe_url("https://slow.example.com", session=session)

        assert result.error == "Timeout"
        assert result.status_code is None
        assert result.is_healthy is False

    @pytest.mark.asyncio
    async def test_connection_error(self) -> None:
        import aiohttp

        session = MagicMock()
        os_error = OSError("Connection refused")
        conn_key = MagicMock()
        session.get = MagicMock(
            side_effect=aiohttp.ClientConnectorError(conn_key, os_error)
        )

        result = await probe_url("https://down.example.com", session=session)

        assert result.error is not None
        assert "Connection error" in result.error

    @pytest.mark.asyncio
    async def test_redirect_chain(self) -> None:
        hist_entry = MagicMock()
        hist_entry.url = "http://example.com"
        hist_entry.status = 301

        mock_resp = _make_mock_response(200, history=[hist_entry])
        session = MagicMock()
        session.get = MagicMock(return_value=mock_resp)

        result = await probe_url("http://example.com", session=session)

        assert len(result.redirect_chain) == 1
        assert result.redirect_chain[0].status_code == 301


class TestProbeMany:
    @pytest.mark.asyncio
    async def test_probe_many_concurrent(self) -> None:
        with patch("webprobe.checker.probe_url") as mock_probe:
            mock_probe.return_value = ProbeResult(
                url="https://example.com", status_code=200, response_time_ms=50.0
            )
            results = await probe_many(
                ["https://a.com", "https://b.com"], concurrency=2
            )
            assert len(results) == 2


# ---------------------------------------------------------------------------
# Output tests
# ---------------------------------------------------------------------------

class TestOutputFormatters:
    def _sample_results(self) -> list[ProbeResult]:
        return [
            ProbeResult(
                url="https://example.com",
                status_code=200,
                response_time_ms=150.5,
                ssl_days_remaining=90,
            ),
            ProbeResult(url="https://bad.example.com", error="Timeout"),
        ]

    def test_render_json(self) -> None:
        results = self._sample_results()
        output = render_json(results)
        data = json.loads(output)
        assert len(data) == 2
        assert data[0]["status_code"] == 200
        assert data[1]["error"] == "Timeout"

    def test_render_csv(self) -> None:
        results = self._sample_results()
        output = render_csv(results)
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "url" in lines[0]
        assert "https://example.com" in lines[1]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCli:
    def test_normalise_url_adds_scheme(self) -> None:
        assert _normalise_url("example.com") == "https://example.com"

    def test_normalise_url_preserves_http(self) -> None:
        assert _normalise_url("http://example.com") == "http://example.com"

    def test_normalise_url_preserves_https(self) -> None:
        assert _normalise_url("https://example.com") == "https://example.com"

    def test_no_urls_exits_with_error(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [])
        assert result.exit_code != 0

    def test_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert "webprobe" in result.output
        assert result.exit_code == 0

    def test_help_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert "WebProbe" in result.output
        assert result.exit_code == 0

    def test_file_input(self, tmp_path: pytest.TempPathFactory) -> None:
        url_file = tmp_path / "urls.txt"  # type: ignore[operator]
        url_file.write_text("https://example.com\n# comment\n\nhttps://google.com\n")

        with patch("webprobe.cli.probe_many") as mock_probe:
            mock_probe.return_value = [
                ProbeResult(url="https://example.com", status_code=200, response_time_ms=50),
                ProbeResult(url="https://google.com", status_code=200, response_time_ms=60),
            ]
            runner = CliRunner()
            result = runner.invoke(main, ["-f", str(url_file), "-o", "json"])
            data = json.loads(result.output)
            assert len(data) == 2

    def test_json_output(self) -> None:
        with patch("webprobe.cli.probe_many") as mock_probe:
            mock_probe.return_value = [
                ProbeResult(url="https://example.com", status_code=200, response_time_ms=50),
            ]
            runner = CliRunner()
            result = runner.invoke(main, ["https://example.com", "-o", "json"])
            data = json.loads(result.output)
            assert data[0]["url"] == "https://example.com"

    def test_csv_output(self) -> None:
        with patch("webprobe.cli.probe_many") as mock_probe:
            mock_probe.return_value = [
                ProbeResult(url="https://example.com", status_code=200, response_time_ms=50),
            ]
            runner = CliRunner()
            result = runner.invoke(main, ["https://example.com", "-o", "csv"])
            assert "url" in result.output
            assert "https://example.com" in result.output
