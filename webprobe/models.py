"""Data models for probe results."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class RedirectHop:
    """A single hop in a redirect chain."""

    url: str
    status_code: int


@dataclass
class ProbeResult:
    """Result of probing a single URL."""

    url: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    content_length: Optional[int] = None
    ssl_expiry: Optional[dt.datetime] = None
    ssl_days_remaining: Optional[int] = None
    redirect_chain: list[RedirectHop] = field(default_factory=list)
    final_url: Optional[str] = None
    error: Optional[str] = None
    timestamp: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))

    @property
    def is_healthy(self) -> bool:
        """Return True if the probe succeeded with a 2xx status."""
        return self.error is None and self.status_code is not None and 200 <= self.status_code < 400

    @property
    def ssl_warning(self) -> bool:
        """Return True if SSL certificate expires within 30 days."""
        return self.ssl_days_remaining is not None and self.ssl_days_remaining <= 30

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain dictionary for JSON/CSV export."""
        return {
            "url": self.url,
            "status_code": self.status_code,
            "response_time_ms": round(self.response_time_ms, 2) if self.response_time_ms else None,
            "content_length": self.content_length,
            "ssl_expiry": self.ssl_expiry.isoformat() if self.ssl_expiry else None,
            "ssl_days_remaining": self.ssl_days_remaining,
            "redirect_chain": [
                {"url": h.url, "status_code": h.status_code} for h in self.redirect_chain
            ],
            "final_url": self.final_url,
            "error": self.error,
            "healthy": self.is_healthy,
            "timestamp": self.timestamp.isoformat(),
        }
