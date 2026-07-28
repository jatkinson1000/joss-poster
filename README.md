# JOSS poster

Source files for a JOSS poster, most recently presented at
[RSECon26](https://rsecon26.society-rse.org/) (Sheffield, UK, September 2026).

Made using the [`tikzposter`](https://ctan.org/pkg/tikzposter) LaTeX
class.

`make` will download some images and compile the poster (basically
with `pdflatex joss-poster`).

You may need to install some LaTeX packages.

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
