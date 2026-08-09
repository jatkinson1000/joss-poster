# JOSS poster

Source files for a JOSS poster, most recently presented at
[RSECon26](https://rsecon26.society-rse.org/) (Sheffield, UK, September 2026).

Made using the [`tikzposter`](https://ctan.org/pkg/tikzposter) LaTeX
class.

`make` will download some images and compile the poster (basically
with `pdflatex joss-poster`).

You may need to install some LaTeX packages, including `texlive-fonts-extra`.

Licensed under a [Creative Commons Attribution 4.0 International
License](https://creativecommons.org/licenses/by/4.0/).

## Scripts

The `scripts/` directory contains Python utilities for regenerating the
poster's content for the current date using the
[Crossref API](https://api.crossref.org).

- `generate_papers_plot.py` — fetches all JOSS articles and regenerates
  the `joss-papers-per-year.png` figure.
  Requires [matplotlib](https://matplotlib.org); can be run with
  [`uv`](https://docs.astral.sh/uv/):
  ```
  uv run scripts/generate_papers_plot.py
  ```
- `most_cited.py` — fetches the top-5 most-cited JOSS articles and prints
  them as a list (citation counts, dates, DOIs, titles):
  ```
  python3 scripts/most_cited.py                  # top 5 (default)
  ```
- `pre_review_rejections.py` — counts JOSS submissions and pre-review
  rejections per year from the issues of
  [openjournals/joss-reviews](https://github.com/openjournals/joss-reviews),
  and regenerates the `joss-rejections-per-year.png` figure.
  Queries use the [GitHub CLI](https://cli.github.com), which must be
  installed. Counts are cached to `scripts/pre_review_rejections.json`:
  ```
  uv run scripts/pre_review_rejections.py             # fetch, print, plot
  uv run scripts/pre_review_rejections.py --use-json  # replot cached counts
  ```
- `papers_by_track.py` — counts published JOSS papers per subject track
  and prints the breakdown:
  ```
  uv run scripts/papers_by_track.py
  ```
