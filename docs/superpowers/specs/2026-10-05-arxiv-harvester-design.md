# Design: #16 arXiv q-fin harvester

Date: 2026-10-05. Branch `issue16-arxiv-harvest`.

## harvest_arxiv.py (new)

Single route: the arXiv API (`export.arxiv.org/api/query`), Atom response.

- `--limit N` (default 100, **hard cap 1000**), `--categories` (default
  `q-fin*,econ.EM,econ.GN`), `--sleep` (default 3.0 — arXiv courtesy limit),
  `--out` (default `data/articles.jsonl`).
- `q-fin*` expands to the 8 q-fin subcategories
  (CP, GN, MF, PM, PR, RM, ST, TR) OR'd; concrete categories pass through.
  search_query: `(cat:X OR cat:Y ...)`, sortBy=submittedDate, descending,
  pages of 100 via `start` until `--limit` or exhaustion.
- Row contract: `entry_row()` from harvest.py; `source: "arXiv"`;
  slug = `arxiv-<slugify(title)>`; url = `https://arxiv.org/abs/<id>`
  (version-stripped); blurb = abstract (full); posted = published date.
- **Abstract as body**: the page file (`fetch.page_path(url)`) is written
  directly with fetch.py's page format; row gets `stage: "fetched"`,
  `page`, `page_chars`. fetch.py skips these rows untouched.
- Dedupe: arXiv id vs existing urls in the jsonl (and the current run).
- Title/summary whitespace-normalized (Atom feeds carry embedded newlines).

## fetch.py / downstream

No changes — rows enter the pipeline already `fetched`.

## README

Stages line + source note.

## Tests (`tests/test_harvest_arxiv.py`)

Atom fixture parse (title/summary/date/author, whitespace normalize); `q-fin*`
category expansion; search_query assembly; page-cache write in fetch format;
slug prefix; dedupe on rerun; limit cap enforcement; pagination stop on short
page; main_with with monkeypatched transport.
