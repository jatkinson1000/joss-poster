#!/usr/bin/env python3
"""
Fetch the most-cited JOSS articles from Crossref and print them as a list.

Data source: Crossref REST API for ISSN 2475-9066 (Journal of Open Source
Software), sorted by `is-referenced-by-count` in descending order.

Fetched using `urllib` from the standard library.

Usage:
    python3 scripts/most_cited.py                       # top 5
    python3 scripts/most_cited.py --top 10              # top 10
    python3 scripts/most_cited.py -o most_cited.txt     # write to file
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ISSN = "2475-9066"
CROSSREF_URL = (
    f"https://api.crossref.org/journals/{ISSN}/works"
    "?filter=type:journal-article"
    "&select=DOI,title,published,is-referenced-by-count"
    "&sort=is-referenced-by-count&order=desc"
)
MAILTO = "jwa34@cam.ac.uk"  # polite-pool: Crossref asks for a contact address


def fetch_most_cited(top: int) -> list[dict]:
    """
    Fetch the top-N most-cited JOSS articles from Crossref via `urllib`.

    Parameters
    ----------
    top : int
        Number of articles to retrieve (passed to the API `rows` parameter).

    Returns
    -------
    list[dict]
        Crossref article records sorted by citation count (descending). Each
        record contains `DOI`, `title`, `published`, and
        `is-referenced-by-count` fields.

    Raises
    ------
    urllib.error.URLError
        If the request to the Crossref API fails or times out.
    RuntimeError
        If the API response is malformed / empty.
    """
    url = f"{CROSSREF_URL}&rows={top}&mailto={MAILTO}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.load(resp)
    items = data["message"].get("items", [])
    if not items:
        raise RuntimeError("Crossref returned no items.")
    print(f"Fetched top {len(items)} most-cited JOSS articles.", file=sys.stderr)
    return items


def _format_date(published: dict) -> str:
    """
    Format a Crossref `published` date-parts field as YYYY-MM-DD.

    Parameters
    ----------
    published : dict
        The `published` field from a Crossref record, expected to contain
        a `date-parts` list.

    Returns
    -------
    str
        Date string in `YYYY-MM-DD` format, with `??` for missing
        month/day components.
    """
    dp = published.get("date-parts", [[None]])
    parts = dp[0] if dp and dp[0] else []
    y = parts[0] if len(parts) > 0 and parts[0] else "????"
    m = f"{parts[1]:02d}" if len(parts) > 1 and parts[1] else "??"
    d = f"{parts[2]:02d}" if len(parts) > 2 and parts[2] else "??"
    return f"{y}-{m}-{d}"


def format_list(works: list[dict]) -> str:
    """
    Format article records as an aligned text list.

    Parameters
    ----------
    works : list[dict]
        Crossref article records from `fetch_most_cited`.

    Returns
    -------
    str
        Column-aligned list with rank, citations, date, DOI, and title.
    """
    lines = [f"{'#':>2}  {'Cites':>7}  {'Date':<11}  {'DOI':<26}  Title"]
    lines.append("-" * 90)
    for i, w in enumerate(works, 1):
        cites = f"{w.get('is-referenced-by-count', 0):,}"
        date_str = _format_date(w.get("published", {}))
        doi = w["DOI"]
        title = w.get("title", ["(untitled)"])[0]
        lines.append(f"{i:>2}  {cites:>7}  {date_str:<11}  {doi:<26}  {title}")
    return "\n".join(lines)


def main() -> None:
    """
    Entry point: parse arguments, fetch most-cited articles, and print them.

    Fetches the top-N most-cited JOSS articles from Crossref and prints them
    as a human-readable list. Output goes to stdout unless `--output` is
    given.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top",
        type=int,
        default=5,
        help="Number of articles to list (default: 5)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write to this file instead of stdout",
    )
    args = parser.parse_args()

    works = fetch_most_cited(args.top)
    text = format_list(works)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n")
        print(f"Wrote {len(works)} entries to {args.output}", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()
