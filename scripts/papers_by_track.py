#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# ///
"""
Count published JOSS papers by subject track and print the breakdown.

Data: GitHub search API over the issues of https://github.com/openjournals/joss-reviews,
accessed via the GitHub CLI https://cli.github.com (`gh`), which must be installed.
Uses the search helper from pre_review_rejections.py.

Process
-------
Every submission is assigned to one of JOSS's eight subject tracks, recorded
as a GitHub label on its issue ("Track: 1 (AASS)" ... "Track: 8 (MISC)").
For each track the script counts issues labelled "published", i.e. papers
that completed review and were published. Shares are of this total, i.e.
since tracks were introduced.

Note: JOSS introduced the track system in 2023, so papers submitted before
then have no track label and are not counted; everything since is assumed
to be labelled.

Counts are saved to `scripts/papers_by_track.json`.

Usage:
    uv run scripts/papers_by_track.py
"""

import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from pre_review_rejections import REPO, gh_search_total

JSON_PATH = Path(__file__).resolve().parent / "papers_by_track.json"

TRACKS = [
    "Track: 1 (AASS)",
    "Track: 2 (BCM)",
    "Track: 3 (PE)",
    "Track: 4 (SBCS)",
    "Track: 5 (DSAIS)",
    "Track: 6 (ESE)",
    "Track: 7 (CSISM)",
    "Track: 8 (MISC)",
]


@dataclass
class TrackStats:
    """Published-paper count for a single subject track."""

    track: str  # short label, e.g. "1 (AASS)"
    published: int


def fetch_counts() -> list[TrackStats]:
    """
    Count published papers in each track.

    Returns
    -------
    list[TrackStats]
        One entry per track.
    """
    stats: list[TrackStats] = []
    for track in TRACKS:
        short = track.removeprefix("Track: ")
        print(f"Fetching {short}...", file=sys.stderr)
        published = gh_search_total(f'repo:{REPO} label:published label:"{track}"')
        stats.append(TrackStats(short, published))
    return stats


def print_table(stats: list[TrackStats]) -> None:
    """
    Print the per-track counts and shares to stdout.

    Shares are of the total tracked papers, i.e. of papers since the
    track system was introduced (2023) — the stat quoted on the poster.

    Parameters
    ----------
    stats : list[TrackStats]
        Per-track counts as returned by `fetch_counts`.
    """
    total = sum(t.published for t in stats)
    print(f"\nPublished JOSS papers by track ({total} since tracks began, 2023)\n")
    print(f"{'Track':<12}{'Papers':>8}{'Share':>8}")
    for t in stats:
        print(f"{t.track:<12}{t.published:>8}{100 * t.published / total:>7.1f}%")


def main() -> None:
    """
    Entry point: fetch counts, print them, and save a JSON record.

    Fetches per-track published-paper counts via the GitHub CLI, prints a
    table to stdout, and saves a JSON record of the counts alongside the
    script.
    """
    stats = fetch_counts()
    record = {
        "fetched_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
        "source": f"GitHub search API over {REPO} issues (via gh CLI)",
        "tracks": [asdict(t) for t in stats],
    }
    JSON_PATH.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Wrote counts to {JSON_PATH}", file=sys.stderr)

    print_table(stats)


if __name__ == "__main__":
    main()
