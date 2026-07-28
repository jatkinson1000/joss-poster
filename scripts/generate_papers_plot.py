#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "matplotlib>=3.8",
# ]
# ///
"""
Fetch JOSS publication counts from Crossref and plot papers published per year.

Data source: Crossref REST API for ISSN 2475-9066 (Journal of Open Source Software).
The current year is shown as a partial count with a distinct colour and annotation.

Usage:
    uv run scripts/generate_papers_plot.py                 # writes ../joss-papers-per-year.png
    uv run scripts/generate_papers_plot.py -o out.png      # custom output path
    uv run scripts/generate_papers_plot.py --dpi 300       # custom DPI
"""

import argparse
import json
import sys
import time
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt

ISSN = "2475-9066"
CROSSREF_URL = (
    f"https://api.crossref.org/journals/{ISSN}/works"
    "?filter=type:journal-article&select=DOI,published&rows=1000"
)
MAILTO = "jwa34@cam.ac.uk"  # polite-pool: Crossref asks for a contact address


def fetch_all_works() -> list[dict]:
    """
    Page through all JOSS journal-article records via Crossref cursor pagination.

    Pages through the Crossref REST API using cursor pagination, sleeping briefly
    between requests to be gentle on the service. Progress is reported to stderr.

    Returns
    -------
    list[dict]
        All JOSS journal-article records returned by Crossref. Each item is the
        raw `message` entry from the API and contains at least the `DOI` and
        `published` fields (per the `select` query parameter).

    Raises
    ------
    urllib.error.URLError
        If a request to the Crossref API fails or times out.
    """
    url = f"{CROSSREF_URL}&mailto={MAILTO}"
    items: list[dict] = []
    cursor = "*"
    total = None
    while True:
        req = urllib.request.Request(f"{url}&cursor={cursor}")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
        msg = data["message"]
        batch = msg.get("items", [])
        if not batch:
            break
        items.extend(batch)
        if total is None:
            total = msg["total-results"]
            print(
                f"Crossref reports {total} JOSS articles; fetching...", file=sys.stderr
            )
        cursor = msg.get("next-cursor")
        if not cursor or len(items) >= total:
            break
        time.sleep(0.5)  # be gentle on the API
    print(f"Fetched {len(items)} records.", file=sys.stderr)
    return items


def count_by_year(works: list[dict]) -> dict[int, int]:
    """
    Bin works into publication years from the published date-parts.

    Parameters
    ----------
    works : list[dict]
        JOSS article records from `fetch_all_works`. Each record is
        expected to have a `published.date-parts` field, as returned by the
        Crossref API.

    Returns
    -------
    dict[int, int]
        Mapping of publication year to number of articles, sorted by year.
        Records missing a publication date are skipped (a warning is printed
        to stderr).
    """
    counts: Counter[int] = Counter()
    missing = 0
    for w in works:
        dp = w.get("published", {}).get("date-parts", [[None]])
        year = dp[0][0] if dp and dp[0] else None
        if year is None:
            missing += 1
        else:
            counts[year] += 1
    if missing:
        print(f"Warning: {missing} records had no publication date.", file=sys.stderr)
    return dict(sorted(counts.items()))


def plot(year_counts: dict[int, int], output: Path, dpi: int) -> None:
    """
    Render a bar chart of papers published per year and save it to a file.

    The current (incomplete) year is shown in distinct colour with a `(partial)`
    annotation, since its count is still accumulating.

    Parameters
    ----------
    year_counts : dict[int, int]
        Mapping of publication year to article count, as returned by
        `count_by_year`.
    output : pathlib.Path
        Destination path for the PNG image.
    dpi : int
        Resolution (dots per inch) of the saved image.
    """

    BAR_COLOUR = "#1F77B4"
    PART_YEAR_COLOUR = "#9C9C9C"
    current_year = datetime.now(tz=timezone.utc).year
    years = sorted(year_counts)
    values = [year_counts[y] for y in years]
    colours = [BAR_COLOUR if y != current_year else PART_YEAR_COLOUR for y in years]

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=dpi)
    bars = ax.bar(years, values, color=colours, edgecolor="white", linewidth=0.5)

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:,}",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    if current_year in year_counts:
        ax.annotate(
            f"{datetime.now(tz=timezone.utc).strftime('%b')} {current_year}\n(partial)",
            xy=(current_year, year_counts[current_year]),
            xytext=(0, 22),
            textcoords="offset points",
            ha="center",
            fontsize=8,
            color=PART_YEAR_COLOUR,
        )

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Papers published", fontsize=12)
    ax.set_title("JOSS publications per year", fontsize=14, fontweight="bold")
    ax.set_xticks(years)
    ax.tick_params(axis="x", rotation=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)
    fig.tight_layout()

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    print(f"Saved plot to {output}", file=sys.stderr)


def main() -> None:
    """
    Entry point: parse arguments, fetch data, and generate the plot.

    Fetches all JOSS article records from Crossref, bins them by publication
    year, prints the per-year counts to stderr, and writes a bar chart to the
    output path (defaulting to `joss-papers-per-year.png` in the repo root).
    """
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=repo_root / "joss-papers-per-year.png",
        help="Output image path (default: repo root joss-papers-per-year.png)",
    )
    parser.add_argument(
        "--dpi", type=int, default=200, help="Output DPI (default: 200)"
    )
    args = parser.parse_args()

    works = fetch_all_works()
    year_counts = count_by_year(works)
    for y, c in sorted(year_counts.items()):
        print(f"  {y}: {c}", file=sys.stderr)
    plot(year_counts, args.output, args.dpi)


if __name__ == "__main__":
    main()
