# Design: #12 multi-LLM compare + #13 Cboe Insights harvester

Date: 2026-10-03

## Issue #12 — optional multi-LLM comparison for codegen

Off by default; normal runs unchanged. Branch `issue12-compare-models`.

### llm.py
- `parse_compare(spec: str) -> list[tuple[str, str]]`: split on `,`, parse `label=cmd`.
  No `=` → label = last `--model <x>` value, else 6-char hash of cmd. Errors on empty
  label/cmd or duplicate labels.
- Refactor `build_argv` into `_build_argv_from(template, model, extra)`; env-var path
  is a wrapper. Behavior unchanged.
- `preflight()` also preflights every `AUTOQUANT_LLM_COMPARE` candidate's binary.

### codegen.py
- `--compare-models "label=cmd,label=cmd"` flag, env fallback `AUTOQUANT_LLM_COMPARE`.
- When set, normal codegen bypassed: per pending spec, prompt runs once per candidate;
  each result publishes via existing `publish` machinery into
  `strategies/compare/<label>/<slug>.py` (+ `.error` markers). `pending_specs` and
  backtest never see the subdir (they glob `strategies/*.py` flat).
- Circuit breaker per label (k consecutive CLI failures aborts that label only).
- Summary table per label: attempted / smoke-passed / smoke-failed / CLI-failed /
  median wall time.
- `--pick <label> --slug <slug>`: candidate must exist and have passed smoke;
  promoted atomically to `strategies/<slug>.py`, `.error` cleared.

### Tests
`tests/test_codegen_compare.py`: parse_compare; namespacing invisible to
pending_specs; fan-out writes per-label artifacts; smoke-fail → per-label `.error`;
`--pick` promotion; preflight covers candidates.

## Issue #13 — Cboe Insights harvester

Branch `issue13-cboe-harvest`.

### harvest_cboe.py (new)
- Imports `entry_row`, `slugify` from `harvest.py`; final slug = `cboe-<slugify(title)>`.
- Default: RSS `https://www.cboe.com/insights/rss/` (~25 latest; parse
  title/link/pubDate/description via xml.etree) — daily incremental mode.
- `--backfill N`: walk `/insights/?page=1..N` listing pages for post URLs; per-page
  error tolerance, `--sleep` politeness (default 2.0).
- Browser-like User-Agent (Cloudflare). Rows appended to `data/articles.jsonl`,
  `source: "Cboe Insights"`, `stage: "harvested"`, deduped on url.
- `--out` like harvest.py.

### fetch.py
- Add `".prose"` to `CANDIDATES`.

### README.md
- Source note for Cboe Insights.

### Tests
`tests/test_harvest_cboe.py`: RSS fixture parse; backfill listing parse; slug
prefixing; dedupe; `fetch.extract` on Cboe-like fixture (`.prose` container,
boilerplate banners/disclaimer stripped by MIN_CHARS-fallback logic).
