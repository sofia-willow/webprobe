"""Output formatters: table, JSON, CSV."""

from __future__ import annotations

import csv
import io
import json
from typing import Sequence

from rich.console import Console
from rich.table import Table

from webprobe.models import ProbeResult


def _status_style(code: int | None) -> tuple[str, str]:
    """Return (display_text, rich_style) for an HTTP status code."""
    if code is None:
        return ("—", "dim")
    if 200 <= code < 300:
        return (str(code), "bold green")
    if 300 <= code < 400:
        return (str(code), "bold yellow")
    if 400 <= code < 500:
        return (str(code), "bold red")
    return (str(code), "bold magenta")


def _health_icon(result: ProbeResult) -> str:
    if result.error:
        return "[bold red]✘[/]"
    if result.is_healthy:
        return "[bold green]✔[/]"
    return "[bold yellow]⚠[/]"


def render_table(results: Sequence[ProbeResult], *, console: Console | None = None) -> None:
    """Print results as a color-coded Rich table."""
    console = console or Console()
    table = Table(title="🔍 WebProbe Results", show_lines=True)
    table.add_column("", justify="center", width=3)
    table.add_column("URL", style="cyan", max_width=50)
    table.add_column("Status", justify="center")
    table.add_column("Time (ms)", justify="right")
    table.add_column("SSL Days", justify="right")
    table.add_column("Redirects", justify="center")
    table.add_column("Error", style="red", max_width=35)

    for r in results:
        status_text, status_style = _status_style(r.status_code)
        time_str = f"{r.response_time_ms:.0f}" if r.response_time_ms is not None else "—"

        ssl_str = "—"
        if r.ssl_days_remaining is not None:
            ssl_style = "red" if r.ssl_warning else "green"
            ssl_str = f"[{ssl_style}]{r.ssl_days_remaining}[/]"

        redirects = str(len(r.redirect_chain)) if r.redirect_chain else "0"

        table.add_row(
            _health_icon(r),
            r.url,
            f"[{status_style}]{status_text}[/]",
            time_str,
            ssl_str,
            redirects,
            r.error or "",
        )

    console.print(table)


def render_json(results: Sequence[ProbeResult]) -> str:
    """Serialize results as a JSON string."""
    return json.dumps([r.to_dict() for r in results], indent=2, default=str)


def render_csv(results: Sequence[ProbeResult]) -> str:
    """Serialize results as CSV."""
    buf = io.StringIO()
    fieldnames = [
        "url",
        "status_code",
        "response_time_ms",
        "content_length",
        "ssl_expiry",
        "ssl_days_remaining",
        "redirects",
        "final_url",
        "error",
        "healthy",
        "timestamp",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in results:
        d = r.to_dict()
        d["redirects"] = len(r.redirect_chain)
        del d["redirect_chain"]
        writer.writerow(d)
    return buf.getvalue()
