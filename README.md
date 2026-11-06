# Paths Forward Georgia

A parent-facing site that compares the paths after high school — four-year college, technical college and trades, apprenticeship, military, a company "work path," and entrepreneurship — using the same measures for each, with every number tagged by source and data quality.

**Status:** prototype, gathering feedback.

## What's here

- `index.html` — the whole site in one file (no build step). Views are hash routes:
  - `#home` — headline stats, earnings-by-education chart, path cards
  - `#compare` — all six paths side by side
  - `#college`, `#technical`, `#apprenticeship`, `#military`, `#work`, `#entrepreneurship` — path pages (looks like at years 1/5/10, who it fits, grade-by-grade guide, numbers, risks, resources)
  - `#calculator` — what-if projection of two profiles' net worth over a working life
  - `#sources` — every source, year, and caveat

## Data

All content lives in one block at the top of the `<script>` in `index.html`:
`SOURCES`, `HEADLINES`, `EDPAYS`, `PATHS`, and `PRESETS` (calculator). Each number carries a `conf` value:

| conf | meaning |
|---|---|
| `strong` | official source, large sample |
| `limited` | partial, national-only, or via a secondary compilation |
| `self` | reported by the program or company itself |

Most figures are national. Georgia-specific data (GA DOL wages, TCSG in-field placement by program, HOPE-adjusted tuition) is the next priority. Figures marked `limited` should be checked against the original tables before any wider launch.

## Calculator assumptions

Today's dollars, smooth average returns, no taxes, no employer matches or stock grants, no scholarships. Salary steps and promotion timing in the presets are assumptions, labeled as such on the page.

## Run locally

Open `index.html` in a browser. Hosted with GitHub Pages from the `main` branch root.

*Not career, legal, or financial advice.*
