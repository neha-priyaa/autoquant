# Workspace (Slice 2) — Design Spec

Date: 2026-10-24. Read-only research workspace replacing the `/workspace` stub.

## Decisions

- Data layer: expanded build-time snapshot (no backend; FastAPI remains slice 3).
- Screens: Overview, Research Feed, Idea Triage, Strategy Lab, Backtests (+detail),
  Leaderboard, Data Catalog. Settings/Docs skipped.
- Sortable tables: TanStack Table (headless). Charts: Recharts later; not in this slice.

## Snapshot v2 (`scripts/web_snapshot.py`)

Keeps the existing landing contract (stages/chains/archive/headline unchanged) and
adds a `workspace` object:

- `articles[]`: slug, title, source, url, posted, stage, triageScore|null (all rows)
- `triage[]`: slug, title, url, claim, assetClass, score, redFlags[], missing[], reason
- `specs[]`: slug, title, claim, universe[], bar, signal, entry, exit, direction,
  status, hasCode, raw (YAML text truncated 4000)
- `runs[]`: every leaderboard row from both lanes: slug, lane, status, netSharpe,
  beatsNull, date, flags[] (article lane), error (external lane)
- `reports{slug}`: {metrics[], text} for every slug with a report
- `failed[]`: slug (from spec path basename), error (truncated 300)
- `catalog[]`: from repo-root `catalog.json` (v1 read data/catalog/index.json, a
  path that does not exist — fixed): id, title, provider, tags, frequency,
  coverageStart, license, notes, fallback

Tolerates missing/malformed files as before (fresh install → empty arrays).

## Workspace UI

- Shell: left sidebar (desktop) / horizontal tab bar (mobile): Overview, Feed,
  Triage, Strategy Lab, Backtests, Leaderboard, Catalog; "← Landing" + theme
  toggle. Routes under /workspace/*; detail views as child routes with slugs.
- Overview: stage strip with per-stage counts, four stat readouts, five latest
  runs, recent failures.
- Feed: all articles, text search + stage filter, expandable rows.
- Triage: sorted by score, claim excerpt, red-flag/missing badges, "LLM
  assessment" tag kept visually distinct from verified backtests.
- Lab: spec rows → detail (structured fields + raw YAML + generated code +
  validation status + link to backtest). Copy buttons.
- Backtests: run list → detail (parsed metrics table, raw report).
- Leaderboard: TanStack Table, column sorting, both lanes, explainable metric.
- Catalog: search over id/title/tags; provider badges; caveats/notes/fallback.

## Testing

Snapshot v2 contract tests per section (present + missing-file cases); loader
tests; component tests per screen (search/filter/sort/detail); gates: vitest,
build, Python suite.
