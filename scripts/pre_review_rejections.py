#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "matplotlib>=3.8",
# ]
# ///
r"""
Count JOSS pre-review rejections by year of submission and plot the results.

Data: GitHub search API over the issues of https://github.com/openjournals/joss-reviews,
accessed via the GitHub CLI https://cli.github.com (`gh`), which must be installed.

Process
-------

1. Every submission becomes an issue titled "[PRE REVIEW]: ...", created at submission.
2. If rejection occurs at pre-review the issue is labelled "rejected" and closed.
   Sometimes papers are instead "withdrawn"; these are included because
   pre-review withdrawals usually follow editorial feedback that a submission
   is unlikely to be accepted (a "soft rejection").
3. A submission that passes has its pre-review issue closed, retaining its
   "[PRE REVIEW]" title, and a new issue opened with "[REVIEW]: ...".

For each year the script queries the issue-search API for:

- submissions: issues created that year titled "[PRE REVIEW]"
  (repo:openjournals/joss-reviews is:issue created:YYYY-01-01..YYYY-12-31
  "PRE REVIEW" in:title).
- pre-review rejections: issues labelled "rejected" whose title contains "[PRE REVIEW]"
  (... label:rejected "PRE REVIEW" in:title);
- withdrawals: issues labelled "withdrawn", also "[PRE REVIEW]"-titled
  (... label:withdrawn "PRE REVIEW" in:title).

The pre-review rejection rate for a year is:

    (pre-review rejections + withdrawals) / submissions

Assumptions
-----------
- Every submission opens a "[PRE REVIEW]"-titled issue that keeps its title
  when closed.
  Then PRE REVIEW-titled issues count submissions exactly, and non-submission
  issues (e.g. tests, meta discussion) are excluded from the totals.
  Verified Aug 2026: all-time review issues match all-time submissions
  passing pre-review to within ~1% (the live pre-review queue).
- 2016 is undercounted.
  In the journal's first year a separate review issue was not always opened,
  so "[PRE REVIEW]"-titled issues miss some 2016 submissions. The numbers
  that year are small, so the effect on the headline rates is negligible.
- [PRE REVIEW] title selects only pre-review rejections.
  Papers that are rejected after review has begn are not included. This is because they
  could be due to factors other than the GenAI changes. Most relevant rejections should
  be caught at pre-review so this effect should be small (approx 4% of rejections come
  during review).
- All issues are labelled correctly
  Some labelling is done by editorialbot, some by editors. There may be
  forgotten/incorrect labels but this is assumed small.
- Data is grouped based on year of submission, not year of rejection.
  This is probably OK. We are interested really in how GenAI has changed JOSS submission
  and evaluation, and a rise in submissions will be the first symptom of any such change.
  The scope also grandfathered in papers in review before the scope changes, and required
  those in pre-review to update to match the new scope.

Raw counts are saved to `scripts/pre_review_rejections.json` and can be
re-plotted without re-querying GitHub (`--use-json`).

Usage:
    uv run scripts/pre_review_rejections.py                 # fetch, print, plot
    uv run scripts/pre_review_rejections.py -o out.png      # custom output path
    uv run scripts/pre_review_rejections.py --use-json      # replot from cache
"""

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = "openjournals/joss-reviews"
FIRST_YEAR = 2016  # JOSS's first submissions
REQUEST_GAP_S = 2.2  # keep us under the 30 req/min search-API limit


@dataclass
class YearStats:
    """Pre-review outcome counts for a single year of submission."""

    submissions: int
    rejected: int
    withdrawn: int

    @property
    def rejection_rate(self) -> float:
        """Fraction of the year's submissions rejected/withdrawn in pre-review."""
        return (self.rejected + self.withdrawn) / self.submissions if self.submissions else 0.0


def gh_search_total(query: str) -> int:
    """
    Return the total_count for a GitHub issue-search query.

    Calls `gh api search/issues -f q=<query> -f per_page=1`, then sleeps
    briefly to stay under GitHub's 30 requests/minute limit.

    Parameters
    ----------
    query : str
        Search qualifiers (e.g. "repo:... created:2016-01-01..2016-12-31").

    Returns
    -------
    int
        Number of matching issues.

    Raises
    ------
    RuntimeError
        If the `gh` command fails (e.g. rate limit exceeded).
    """
    # NB: adding -f fields makes `gh api` default to POST; force GET for search.
    cmd = [
        "gh", "api", "search/issues", "--method", "GET",
        "-f", f"q={query}", "-f", "per_page=1",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(cmd)}` failed with exit code {proc.returncode}:\n"
            f"{proc.stderr.strip()}"
        )
    time.sleep(REQUEST_GAP_S)  # pace requests to stay under 30/min
    return json.loads(proc.stdout)["total_count"]


def fetch_year(year: int) -> YearStats:
    """
    Fetch submission, rejection and withdrawal counts for one year.

    Pre-review rejections are "rejected"-labelled issues whose title is
    still "[PRE REVIEW]", i.e. rejected before proceeding to review.
    Issues rejected during review are not included (see above).

    Withdrawn during pre-review is also collected in a similar fashion.

    Parameters
    ----------
    year : int
        Year of submission (issue creation date) to query.

    Returns
    -------
    YearStats
        Counts for the year.
    """
    window = f"created:{year}-01-01..{year}-12-31"
    base = f"repo:{REPO} is:issue {window}"
    pre_review = '"PRE REVIEW" in:title'
    return YearStats(
        submissions=gh_search_total(f"{base} {pre_review}"),
        rejected=gh_search_total(f"{base} label:rejected {pre_review}"),
        withdrawn=gh_search_total(f"{base} label:withdrawn {pre_review}"),
    )


def fetch_all(first_year: int, last_year: int) -> dict[int, YearStats]:
    """
    Fetch YearStats for each year in [first_year, last_year].

    Parameters
    ----------
    first_year : int
        First year to include.
    last_year : int
        Last year to include.

    Returns
    -------
    dict[int, YearStats]
        Per-year counts keyed by year.
    """
    stats: dict[int, YearStats] = {}
    for year in range(first_year, last_year + 1):
        print(f"Fetching {year}...")
        stats[year] = fetch_year(year)
    return stats


def print_table(stats: dict[int, YearStats]) -> None:
    """
    Print a per-year table and period aggregates.

    Period aggregates summarise the eras discussed on the poster:
    the early years, the pre-generative-AI "mature" period (2020-2024),
    2025, and the current year (after the early-2026 scope update).

    Pre-review rejections and withdrawals are combined for the rejection rate.

    Parameters
    ----------
    stats : dict[int, YearStats]
        Per-year counts as returned by `fetch_all`.
    """
    current_year = datetime.now(tz=timezone.utc).year
    partial = f" (to {datetime.now(tz=timezone.utc):%d %b})"

    print(f"\nPre-review rejections in {REPO}")
    print("(Rejected/withdrawn = closed in pre-review: still titled [PRE REVIEW];\n"
          " in-review rejections/withdrawals are excluded.)\n")
    print(f"{'Year':<12}{'Submissions':>12}{'Rejected':>10}{'Withdrawn':>11}{'Reject %':>10}")
    for year, s in sorted(stats.items()):
        label = f"{year}{partial}" if year == current_year else str(year)
        print(
            f"{label:<12}{s.submissions:>12}{s.rejected:>10}"
            f"{s.withdrawn:>11}{100 * s.rejection_rate:>9.1f}%"
        )

    def aggregate(first: int, last: int) -> str:
        sel = [s for y, s in stats.items() if first <= y <= min(last, current_year)]
        sub = sum(s.submissions for s in sel)
        rej = sum((s.rejected + s.withdrawn) for s in sel)
        return f"{first}-{min(last, current_year)}: {rej}/{sub} = {100 * rej / sub:.1f}%"

    print("\nAggregates:")
    print(f"  {aggregate(FIRST_YEAR, 2019)}")
    print(f"  {aggregate(2020, 2024)}")
    print(f"  {aggregate(2025, 2025)}")
    print(f"  {aggregate(2026, current_year)}")


def plot(stats: dict[int, YearStats], output: Path, dpi: int) -> None:
    """
    Plot submissions and pre-review rejections per year, plus the rejection rate.

    Bars show the number of submissions, and of rejections plus withdrawals
    (left axis); a dashed line with markers shows the rejection rate (right
    axis). The current, incomplete year is drawn in a distinct colour with a
    dagger footnote annotation.

    Parameters
    ----------
    stats : dict[int, YearStats]
        Per-year counts as returned by `fetch_all`.
    output : pathlib.Path
        Destination path for the PNG image.
    dpi : int
        Resolution (dots per inch) of the saved image.
    """
    import matplotlib.pyplot as plt

    BAR_COLOUR = "#1F77B4"
    REJECT_COLOUR = "#E15759"
    PART_YEAR_COLOUR = "#9C9C9C"
    current_year = datetime.now(tz=timezone.utc).year

    years = sorted(stats)
    submissions = [stats[y].submissions for y in years]
    rejected = [(stats[y].rejected + stats[y].withdrawn) for y in years]
    rates = [100 * stats[y].rejection_rate for y in years]
    colours = [PART_YEAR_COLOUR if y == current_year else BAR_COLOUR for y in years]

    # Flatter aspect than the sibling papers-per-year plot, but similar font
    # sizes: both are displayed at (nearly) full block width on the poster.
    fig, ax = plt.subplots(figsize=(8, 3.6), dpi=dpi)
    ax.bar(
        [y - 0.2 for y in years],
        submissions,
        width=0.4,
        color=colours,
        edgecolor="white",
        linewidth=0.5,
        label="Submissions",
    )
    ax.bar(
        [y + 0.2 for y in years],
        rejected,
        width=0.4,
        color=REJECT_COLOUR,
        edgecolor="white",
        linewidth=0.5,
        label="Rejected in pre-review",
    )

    ax2 = ax.twinx()
    ax2.plot(
        years,
        rates,
        color="black",
        marker="o",
        markersize=4,
        linewidth=1.5,
        linestyle="--",
        label="Rejection rate",
    )
    ax2.set_ylabel("Pre-review rejection rate (%)", fontsize=12)
    ax2.set_ylim(bottom=0)

    # Label the three most recent rate points — they carry the poster's message.
    for year, rate, dx, dy in ((years[-3], rates[-3], -14, 10),
                               (years[-2], rates[-2], -14, 10),
                               (years[-1], rates[-1], -6, -20)):
        ax2.annotate(
            f"{rate:.0f}%",
            xy=(year, rate),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=9,
            bbox=dict(facecolor="white", alpha=0.75, edgecolor="none", pad=1.5),
        )

    ax.set_xlabel("Year of submission", fontsize=12)
    ax.set_ylabel("Number of submissions", fontsize=12)
    ax.set_title(
        "JOSS pre-review rejections per year", fontsize=14, fontweight="bold"
    )
    ax.set_xticks(years)
    # Same "partial year" style as generate_papers_plot.py: note above the bar.
    ax.annotate(
        f"{datetime.now(tz=timezone.utc):%b} {current_year}\n(partial)",
        xy=(current_year, submissions[-1]),
        xytext=(0, 3),  # just above the bar; (0, 22) collides with the % label
        textcoords="offset points",
        ha="center",
        fontsize=8,
        color=PART_YEAR_COLOUR,
    )
    ax.spines[["top"]].set_visible(False)
    ax2.spines[["top"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)

    handles1, labels1 = ax.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(handles1 + handles2, labels1 + labels2, loc="upper left", fontsize=10)

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    print(f"Saved plot to {output}", file=sys.stderr)


def main() -> None:
    """
    Entry point: parse arguments, fetch or load data, print and plot the results.

    Fetches yearly submission/rejection/withdrawal counts for the JOSS reviews
    repository via the GitHub CLI, prints a table to stdout, optionally saves a
    JSON record of the raw counts, and plots the trend (defaulting to
    `joss-rejections-per-year.png` in the repo root).
    """
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=repo_root / "joss-rejections-per-year.png",
        help="Output image path (default: repo root joss-rejections-per-year.png)",
    )
    parser.add_argument(
        "--dpi", type=int, default=200, help="Output DPI (default: 200)"
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=Path(__file__).resolve().parent / "pre_review_rejections.json",
        help="Path for the JSON record of counts (default: alongside this script)",
    )
    parser.add_argument(
        "--use-json",
        action="store_true",
        help="Read counts from the JSON record instead of querying GitHub",
    )
    args = parser.parse_args()

    if args.use_json:
        record = json.loads(args.json.read_text())
        stats = {int(y): YearStats(**v) for y, v in record["years"].items()}
        print(f"Loaded counts recorded at {record['fetched_at']} from {args.json}",
              file=sys.stderr)
    else:
        if shutil.which("gh") is None:
            sys.exit(
                "The GitHub CLI (`gh`) is required: https://cli.github.com\n"
                "Install it and authenticate with `gh auth login`."
            )
        current_year = datetime.now(tz=timezone.utc).year
        stats = fetch_all(FIRST_YEAR, current_year)
        record = {
            "fetched_at": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            "source": f"GitHub search API over {REPO} issues (via gh CLI)",
            "years": {str(y): asdict(s) for y, s in stats.items()},
        }
        args.json.write_text(json.dumps(record, indent=2) + "\n")
        print(f"Wrote counts to {args.json}", file=sys.stderr)

    print_table(stats)
    plot(stats, args.output, args.dpi)


if __name__ == "__main__":
    main()
