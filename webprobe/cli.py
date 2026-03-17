"""Command-line interface for webprobe."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from webprobe import __version__
from webprobe.checker import probe_many
from webprobe.output import render_csv, render_json, render_table


def _load_urls_from_file(path: Path) -> list[str]:
    """Read URLs from a file, one per line, skipping blanks and comments."""
    urls: list[str] = []
    with path.open() as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)
    return urls


def _normalise_url(url: str) -> str:
    """Ensure the URL has a scheme."""
    if not url.startswith(("http://", "https://")):
        return f"https://{url}"
    return url


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("urls", nargs=-1)
@click.option(
    "-f",
    "--file",
    "url_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Read URLs from a file (one per line).",
)
@click.option(
    "-o",
    "--output",
    "output_format",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "-c",
    "--concurrency",
    type=int,
    default=20,
    show_default=True,
    help="Maximum concurrent requests.",
)
@click.option(
    "-t",
    "--timeout",
    type=float,
    default=30.0,
    show_default=True,
    help="Per-request timeout in seconds.",
)
@click.option(
    "--no-redirects",
    is_flag=True,
    default=False,
    help="Do not follow HTTP redirects.",
)
@click.option(
    "--save",
    "save_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Save output to a file (works with json/csv).",
)
@click.version_option(version=__version__, prog_name="webprobe")
def main(
    urls: tuple[str, ...],
    url_file: Optional[Path],
    output_format: str,
    concurrency: int,
    timeout: float,
    no_redirects: bool,
    save_path: Optional[Path],
) -> None:
    """🔍 WebProbe — Fast, async website health checker.

    Check response time, status codes, SSL certificate expiry,
    and redirect chains for one or more URLs.

    \b
    Examples:
        webprobe https://example.com https://google.com
        webprobe -f urls.txt -o json --save results.json
        webprobe example.com --timeout 10 --concurrency 5
    """
    console = Console(stderr=True)

    # Collect URLs
    all_urls: list[str] = [_normalise_url(u) for u in urls]
    if url_file:
        all_urls.extend(_normalise_url(u) for u in _load_urls_from_file(url_file))

    if not all_urls:
        console.print("[red]Error:[/] No URLs provided. Pass URLs as arguments or use -f/--file.")
        sys.exit(1)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_urls: list[str] = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    console.print(f"[dim]Probing {len(unique_urls)} URL(s) with concurrency={concurrency}…[/]")

    # Run probes
    results = asyncio.run(
        probe_many(
            unique_urls,
            concurrency=concurrency,
            timeout_seconds=timeout,
            follow_redirects=not no_redirects,
        )
    )

    # Output
    output_text: Optional[str] = None

    if output_format == "table":
        render_table(results, console=Console())
    elif output_format == "json":
        output_text = render_json(results)
        click.echo(output_text)
    elif output_format == "csv":
        output_text = render_csv(results)
        click.echo(output_text, nl=False)

    # Save to file
    if save_path and output_text:
        save_path.write_text(output_text)
        console.print(f"[green]Saved to {save_path}[/]")
    elif save_path and output_format == "table":
        console.print("[yellow]Warning:[/] --save is only supported with json/csv output.")

    # Exit code: non-zero if any probe failed
    if any(not r.is_healthy for r in results):
        sys.exit(1)
