# AutoQuant Web Frontend — Design Spec

Date: 2026-10-20
Status: Approved in conversation
Scope: Slice 1 of the web frontend — design system + public landing page. The
workspace screens and the action/API layer are later slices on the same tokens.

## Goal

A premium, editorial landing experience for AutoQuant that renders **only real
pipeline artifacts** — no fabricated experiments, metrics, or results — and
establishes the design system the future research workspace will inherit.

## Decisions made

- **Stack**: React 18 + TypeScript + Vite + Tailwind v4 + Recharts (later
  slices), Lucide icons. Lives in `autoquant/web/`.
- **Content**: build-time snapshot. `scripts/web_snapshot.py` reads real
  artifacts and emits `web/src/content/snapshot.json` (gitignored). No runtime
  backend in this slice.
- **Motion**: CSS + IntersectionObserver only; no animation library;
  `prefers-reduced-motion` disables all reveal/loop animation.
- **Backend**: untouched. The Python pipeline is never invoked by the UI.

## Architecture

```
autoquant/
├── scripts/web_snapshot.py      # NEW: artifacts -> snapshot JSON (pure readers)
└── web/
    ├── package.json
    ├── index.html
    ├── src/
    │   ├── main.tsx             # app shell: / = landing, /workspace = honest stub
    │   ├── styles/tokens.css    # Tailwind theme + base styles
    │   ├── content/snapshot.json# generated, gitignored
    │   ├── content/snapshot.ts  # typed loader + fallback empty snapshot
    │   ├── components/          # Nav, StageRow, ArchiveRow, MetricReadout,
    │   │                        # StatusDot, ArtifactPanel, Reveal, ...
    │   └── sections/            # Hero, Pipeline, InMotion, Evidence,
    │                            # Archive, FinalCta, Footer
    └── tests/                   # Vitest component tests
```

### Snapshot script (`scripts/web_snapshot.py`)

- Pure readers; imports nothing from the pipeline stages.
- Reads: `data/articles.jsonl`, `data/triage.jsonl`, `specs/*.yaml`,
  `results/leaderboard.jsonl`, `results/failed.jsonl`,
  `results/external/leaderboard.jsonl`, `reports/*.md` (headers only),
  `catalog.json` (count + providers only).
- Emits (typed in `web/src/content/snapshot.ts`):
  - `generatedAt`, `counts` (articles, triaged, specs, backtests, external rows)
  - `stages`: the 01–07 pipeline manifest with the real artifact each produces
  - `chains`: up to 3 real artifact chains — article excerpt (≤400 chars),
    spec YAML (truncated), leaderboard row, report metrics
  - `archive`: leaderboard rows (strategy slug, source, date, status, net
    Sharpe/return) from both leaderboards
  - `headline`: one completed run's metrics exactly as its report emits
  - `catalog`: series count + provider list
- Tolerates missing files (fresh install → valid empty snapshot, `counts: 0`).
- CLI: `uv run python scripts/web_snapshot.py [--out web/src/content/snapshot.json]`.
- pytest coverage: fixture artifacts → expected JSON contract (missing-file and
  present-file cases, truncation limits, metric passthrough).

### App shell

- `/` — landing. `/workspace` — real route with an honest under-construction
  state (links to `reports/`, README) so "Open Workspace" is never fake.
- Snapshot loader falls back to the empty snapshot + dev-only banner
  `SNAPSHOT NOT FOUND — RUN uv run python scripts/web_snapshot.py`.

## Design system

- **Palette**: bg `#0B0C0D`, surface `#131516`, text `#F3F1EA`, secondary
  `#969A97`, accent `#C5F467`, border `rgba(243,241,234,0.13)`. Accent only for
  live status, active states, one CTA.
- **Type**: display face for oversized headlines (`clamp()` up to ~7rem,
  deliberate line breaks); JetBrains Mono for tickers, numbers, IDs, statuses,
  metadata labels (`tabular-nums`). Monumental-vs-technical contrast.
- **Primitives**: thin-border panel, editorial row, stage index, metric
  readout, status dot (ok/warn/fail/pending mapped from real verdicts),
  grid-line background motif.
- Dark-only. WCAG-AA contrast, semantic HTML, visible focus rings.

## Landing sections

1. **Nav** — `AUTOQUANT` wordmark; Product · Pipeline · Experiments ·
   Documentation (→ GitHub README); accent **Open Workspace →**. Mobile:
   full-screen overlay menu. Blur-on-scroll, thin bottom border.
2. **Hero** — two-line headline "Research the idea. / Test the evidence."
   (second line secondary color), supporting copy, mono status chip
   `● PIPELINE IDLE — N ARTIFACTS INDEXED` (real count), two CTAs. Signature
   animation: prose → YAML lines → animated SVG equity trace → mono metric
   readout. Static under reduced motion; `aria` static fallback.
3. **Pipeline (01–07)** — full-width thin-border rows: mono index, stage name,
   one-line real description, right-aligned mono artifact tag
   (`data/triage.jsonl`…). Vertical hairline connector, scroll reveal,
   center-nearest row gets the accent tick. Rows link to README anchors.
4. **Research in motion** — interactive artifact chain from `chains[0]`
   (default: the coherence promotion): article excerpt → spec YAML → generated
   code → report metrics. Keyboard-navigable stage selector; "inspect in repo"
   links; real truncated artifact text only.
5. **Evidence over assumptions** — editorial statement + real metric readouts
   for `headline` (fields exactly as reports emit); disclaimer in secondary
   text; designed empty state when no completed run exists.
6. **Experiment archive** — editorial rows from `archive`: status dot, strategy
   name, source, date, one key metric. Sort by an explicitly selected metric;
   "view all" → `/workspace`.
7. **Final CTA + footer** — "Good research starts with a testable question.",
   Open Workspace, stage list, repo link, evidence disclaimer.

## Error handling

- Missing/stale snapshot → empty snapshot + dev-only banner.
- Malformed artifact lines → skipped by the snapshot script (same tolerance as
  the pipeline's own readers).
- Empty states designed for: no articles, no specs, no leaderboard rows, no
  reports, empty catalog.

## Testing & verification

- pytest: snapshot script contract tests.
- Vitest: snapshot-driven sections (archive rows, empty states, metric
  formatting), status-dot mapping, reduced-motion handling.
- Gates: `tsc --noEmit`, `npm run build`, `npx vitest run`,
  `uv run python -m pytest` all green.
- README: frontend setup, dev/build commands, snapshot regeneration workflow.

## Out of scope (later slices)

- Workspace screens (feed, triage, strategy lab, backtests, leaderboard,
  catalog), FastAPI artifact/action service, pipeline triggering from the UI.
