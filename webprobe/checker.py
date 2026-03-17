"""Core async probe engine."""

from __future__ import annotations

import asyncio
import datetime as dt
import ssl
import time
from typing import Optional, Sequence

import aiohttp

from webprobe.models import ProbeResult, RedirectHop


def _get_ssl_info(transport: object) -> tuple[Optional[dt.datetime], Optional[int]]:
    """Extract SSL certificate expiry from the transport layer."""
    try:
        ssl_object = transport.get_extra_info("ssl_object")  # type: ignore[union-attr]
        if ssl_object is None:
            return None, None
        cert = ssl_object.getpeercert()
        if cert is None:
            return None, None
        not_after = cert.get("notAfter")
        if not_after is None:
            return None, None
        # Format: 'Mon DD HH:MM:SS YYYY GMT'
        expiry = dt.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=dt.timezone.utc
        )
        days_remaining = (expiry - dt.datetime.now(dt.timezone.utc)).days
        return expiry, days_remaining
    except Exception:
        return None, None


async def probe_url(
    url: str,
    *,
    timeout_seconds: float = 30.0,
    follow_redirects: bool = True,
    session: Optional[aiohttp.ClientSession] = None,
) -> ProbeResult:
    """Probe a single URL and return the result.

    Args:
        url: The URL to check.
        timeout_seconds: Maximum wait time per request.
        follow_redirects: Whether to follow redirects (and record the chain).
        session: Optional shared aiohttp session (caller manages lifecycle).

    Returns:
        A ``ProbeResult`` with timing, status, SSL, and redirect data.
    """
    own_session = session is None
    if own_session:
        session = aiohttp.ClientSession()

    redirect_chain: list[RedirectHop] = []
    ssl_context = ssl.create_default_context()

    try:
        start = time.monotonic()
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout_seconds),
            allow_redirects=follow_redirects,
            ssl=ssl_context,
        ) as response:
            elapsed_ms = (time.monotonic() - start) * 1000

            # Collect redirect history
            for hist in response.history:
                redirect_chain.append(
                    RedirectHop(url=str(hist.url), status_code=hist.status)
                )

            # SSL info
            ssl_expiry, ssl_days = _get_ssl_info(response.connection and response.connection.transport)

            content_length = response.content_length

            return ProbeResult(
                url=url,
                status_code=response.status,
                response_time_ms=elapsed_ms,
                content_length=content_length,
                ssl_expiry=ssl_expiry,
                ssl_days_remaining=ssl_days,
                redirect_chain=redirect_chain,
                final_url=str(response.url) if redirect_chain else None,
                error=None,
            )
    except asyncio.TimeoutError:
        return ProbeResult(url=url, error="Timeout")
    except aiohttp.ClientConnectorCertificateError as exc:
        return ProbeResult(url=url, error=f"SSL error: {exc}")
    except aiohttp.ClientConnectorError as exc:
        return ProbeResult(url=url, error=f"Connection error: {exc}")
    except aiohttp.ClientError as exc:
        return ProbeResult(url=url, error=f"HTTP error: {exc}")
    except Exception as exc:
        return ProbeResult(url=url, error=str(exc))
    finally:
        if own_session:
            await session.close()


async def probe_many(
    urls: Sequence[str],
    *,
    concurrency: int = 20,
    timeout_seconds: float = 30.0,
    follow_redirects: bool = True,
) -> list[ProbeResult]:
    """Probe multiple URLs concurrently.

    Args:
        urls: URLs to check.
        concurrency: Max simultaneous connections.
        timeout_seconds: Per-request timeout.
        follow_redirects: Follow HTTP redirects.

    Returns:
        A list of ``ProbeResult`` objects (order matches input).
    """
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=ssl.create_default_context())
    async with aiohttp.ClientSession(connector=connector) as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def _limited(url: str) -> ProbeResult:
            async with semaphore:
                return await probe_url(
                    url,
                    timeout_seconds=timeout_seconds,
                    follow_redirects=follow_redirects,
                    session=session,
                )

        return list(await asyncio.gather(*(_limited(u) for u in urls)))
