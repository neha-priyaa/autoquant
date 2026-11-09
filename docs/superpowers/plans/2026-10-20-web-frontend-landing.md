# AutoQuant Web Landing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship slice 1 of the AutoQuant web frontend — the design system plus an editorial landing page that renders only real pipeline artifacts via a build-time snapshot.

**Architecture:** `scripts/web_snapshot.py` reads the repo's real artifacts (jsonl/yaml/md, tolerant of missing files) and emits typed `web/src/content/snapshot.json`. A React 18 + Vite + Tailwind v4 app in `web/` renders the landing from that snapshot at `/`, with an honest `/workspace` stub. No runtime backend; the Python pipeline is untouched.

**Tech Stack:** Python 3.11 + pyyaml (snapshot script, pytest), React 18, TypeScript, Vite 6, Tailwind v4 (`@tailwindcss/vite`), react-router-dom 6, lucide-react, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-20-web-frontend-design.md`

---

## File structure

```
scripts/web_snapshot.py            # snapshot builder (pure readers, CLI)
tests/test_web_snapshot.py         # its contract tests
web/
├── package.json                   # deps + scripts (dev/build/preview/test)
├── index.html                     # fonts + root
├── tsconfig.json, vite.config.ts  # toolchain
├── src/
│   ├── main.tsx                   # router: / landing, /workspace stub
│   ├── styles/tokens.css          # Tailwind theme + base + motion styles
│   ├── content/snapshot.ts        # types + loader + empty fallback
│   ├── content/snapshot.json      # generated (gitignored)
│   ├── lib/reveal.ts              # IntersectionObserver hook
│   ├── components/
│   │   ├── StatusDot.tsx          # verdict -> colored dot
│   │   ├── MetricReadout.tsx      # mono label/value pair
│   │   ├── Reveal.tsx             # scroll-reveal wrapper
│   │   ├── Nav.tsx                # top nav + mobile overlay
│   │   └── Footer.tsx
│   └── sections/
│       ├── Hero.tsx               # headline + prose->YAML->curve animation
│       ├── Pipeline.tsx           # 01-07 stage rows
│       ├── InMotion.tsx           # interactive artifact chain
│       ├── Evidence.tsx           # real headline metrics + disclaimer
│       ├── Archive.tsx            # leaderboard editorial rows + sort
│       ├── FinalCta.tsx
│       └── WorkspaceStub.tsx      # honest /workspace state
└── tests/
    ├── snapshot.test.ts
    └── sections.test.tsx
```

---

### Task 1: Snapshot script — empty-install contract (TDD)

**Files:**
- Create: `tests/test_web_snapshot.py`
- Create: `scripts/web_snapshot.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_web_snapshot.py
"""Contract tests for scripts/web_snapshot.py — builds snapshot JSON from
real artifacts; must tolerate a fresh install with no artifacts at all."""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module(root: Path):
    spec = importlib.util.spec_from_file_location(
        "web_snapshot", root / "scripts" / "web_snapshot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEmptyInstall:
    def test_missing_everything_yields_valid_empty_snapshot(self, tmp_path):
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        assert snap["counts"] == {"articles": 0, "triaged": 0, "specs": 0,
                                  "backtests": 0, "external": 0}
        assert snap["chains"] == [] and snap["archive"] == []
        assert snap["headline"] is None
        assert snap["catalog"] == {"series": 0, "providers": []}
        assert len(snap["stages"]) == 7
        assert snap["generatedAt"]

    def test_stages_describe_real_artifacts(self, tmp_path):
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        artifacts = " ".join(s["artifact"] for s in snap["stages"])
        assert "data/articles.jsonl" in artifacts
        assert "data/triage.jsonl" in artifacts
        assert "specs/" in artifacts
        assert "results/leaderboard.jsonl" in artifacts


class TestCountsAndArchive:
    def test_counts_from_real_files(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "results").mkdir()
        (tmp_path / "data" / "articles.jsonl").write_text(
            json.dumps({"slug": "a", "title": "A", "url": "https://x",
                        "source": "S", "posted": "2026-01-01",
                        "blurb": "b", "stage": "fetched"}) + "\n"
            + "torn line\n")
        (tmp_path / "results" / "leaderboard.jsonl").write_text(
            json.dumps({"slug": "a", "verdict": "PENDING", "net_sharpe": 1.5,
                        "beats_null_95": True, "run_at": "2026-02-01T00:00:00"}) + "\n")
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "a.yaml").write_text(
            "meta:\n  slug: a\n  title: A\n  source: S\n")
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        assert snap["counts"] == {"articles": 1, "triaged": 0, "specs": 1,
                                  "backtests": 1, "external": 0}
        assert snap["archive"][0]["slug"] == "a"
        assert snap["archive"][0]["netSharpe"] == 1.5
        assert snap["archive"][0]["lane"] == "article"

    def test_external_rows_land_in_archive(self, tmp_path):
        (tmp_path / "results" / "external").mkdir(parents=True)
        (tmp_path / "results" / "external" / "leaderboard.jsonl").write_text(
            json.dumps({"repo": "o/r", "artifact": "n.ipynb", "kind": "notebook",
                        "verdict": "ok", "runtime_s": 2.0,
                        "run_at": "2026-03-01T00:00:00Z"}) + "\n")
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        row = snap["archive"][0]
        assert row["lane"] == "external" and row["source"] == "o/r"
        assert snap["counts"]["external"] == 1


class TestHeadlineAndChains:
    def test_headline_parses_report_table(self, tmp_path):
        (tmp_path / "results").mkdir()
        (tmp_path / "results" / "leaderboard.jsonl").write_text(
            json.dumps({"slug": "a", "verdict": "PENDING", "net_sharpe": -0.04,
                        "beats_null_95": False, "run_at": "2026-02-01T00:00:00"}) + "\n")
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "a.md").write_text(
            "# A strategy\n\n## Headline (net of costs)\n\n"
            "| | strategy | buy & hold |\n|---|---|---|\n"
            "| CAGR | -7.44% | 10.82% |\n| Sharpe | -0.04 | 0.461 |\n"
            "| max DD | -51.18% | -66.00% |\n| trades | 62 | 1 |\n")
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        h = snap["headline"]
        assert h["slug"] == "a"
        metrics = {m["label"]: m for m in h["metrics"]}
        assert metrics["Sharpe"]["strategy"] == "-0.04"
        assert metrics["trades"]["benchmark"] == "1"

    def test_chain_assembles_real_artifacts(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "results").mkdir()
        (tmp_path / "reports").mkdir()
        (tmp_path / "specs").mkdir()
        (tmp_path / "strategies").mkdir()
        (tmp_path / "data" / "articles.jsonl").write_text(
            json.dumps({"slug": "a", "title": "A", "url": "https://x",
                        "source": "S", "posted": "2026-01-01",
                        "blurb": "word " * 100, "stage": "fetched"}) + "\n")
        (tmp_path / "results" / "leaderboard.jsonl").write_text(
            json.dumps({"slug": "a", "verdict": "PENDING", "net_sharpe": 1.0,
                        "beats_null_95": True, "run_at": "2026-02-01T00:00:00"}) + "\n")
        (tmp_path / "specs" / "a.yaml").write_text("meta:\n  slug: a\n" + "x: 1\n" * 500)
        (tmp_path / "strategies" / "a.py").write_text("import pandas\n" * 200)
        (tmp_path / "reports" / "a.md").write_text(
            "## Headline (net of costs)\n\n| | strategy | buy & hold |\n"
            "|---|---|---|\n| Sharpe | 1.0 | 0.5 |\n")
        ws = load_module(ROOT)
        snap = ws.build_snapshot(tmp_path)
        chain = snap["chains"][0]
        kinds = [s["kind"] for s in chain["stages"]]
        assert kinds == ["article", "spec", "code", "report"]
        assert len(chain["stages"][0]["body"]) <= 400
        assert len(chain["stages"][1]["body"]) <= 1200
        assert len(chain["stages"][2]["body"]) <= 1200

    def test_cli_writes_file(self, tmp_path, capsys):
        ws = load_module(ROOT)
        out = tmp_path / "out" / "snapshot.json"
        rc = ws.main_with([f"--root", str(tmp_path), "--out", str(out)])
        assert rc == 0 and json.loads(out.read_text())["generatedAt"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_web_snapshot.py -v`
Expected: FAIL — `FileNotFoundError` for `scripts/web_snapshot.py`

- [ ] **Step 3: Write the implementation**

```python
#!/usr/bin/env python3
"""WEB SNAPSHOT — build web/src/content/snapshot.json from real artifacts.

Pure readers over the pipeline's output artifacts (jsonl/yaml/md). Never
executes the pipeline, never fabricates content: a fresh install produces a
valid all-empty snapshot and the landing renders its empty states.

    uv run python scripts/web_snapshot.py [--out web/src/content/snapshot.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "web" / "src" / "content" / "snapshot.json"

MAX_BLURB = 400
MAX_ARTIFACT = 1200
MAX_ARCHIVE = 12
MAX_CHAINS = 3

STAGES = [
    ("01", "Discover research",
     "Pull candidate strategy write-ups from Quantocracy, Cboe Insights and "
     "arXiv q-fin feeds.", "data/articles.jsonl"),
    ("02", "Fetch source material",
     "Extract and cache the full article text behind every discovered link.",
     "data/pages/"),
    ("03", "Evaluate testability",
     "Score every claim: is it a testable hypothesis, and do we have the data?",
     "data/triage.jsonl"),
    ("04", "Extract a specification",
     "Turn a triaged claim into an explicit YAML spec — universe, signal, "
     "rules, costs, validation.", "specs/"),
    ("05", "Generate strategy code",
     "Generate Python for the spec and smoke-test it before anything runs.",
     "strategies/"),
    ("06", "Execute an isolated backtest",
     "Run every spec in a timeout-capped subprocess against the local price "
     "cache.", "results/leaderboard.jsonl"),
    ("07", "Compare and inspect",
     "Rank the evidence on one explainable metric and read the full reports.",
     "reports/"),
]

METRIC_LABELS = re.compile(
    r"^(CAGR|Sharpe|max DD|t-stat|exposure|trades|win rate|profit factor|"
    r"Gross Sharpe|Deflated Sharpe)$", re.I)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " …"


def report_metrics(report_path: Path) -> list[dict]:
    """Metric rows from a report's Headline table: label / strategy / benchmark."""
    if not report_path.exists():
        return []
    metrics = []
    for line in report_path.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and METRIC_LABELS.match(cells[0]):
            metrics.append({"label": cells[0], "strategy": cells[1],
                            "benchmark": cells[2]})
    return metrics


def _leaderboard(root: Path) -> list[dict]:
    return load_jsonl(root / "results" / "leaderboard.jsonl")


def _archive_row_article(row: dict, root: Path) -> dict | None:
    slug = row.get("slug")
    if not slug:
        return None
    source = "research lane"
    spec_path = root / "specs" / f"{slug}.yaml"
    if spec_path.exists():
        try:
            meta = (yaml.safe_load(spec_path.read_text()) or {}).get("meta", {})
            source = meta.get("source") or source
        except yaml.YAMLError:
            pass
    return {"slug": slug, "source": source, "lane": "article",
            "status": row.get("verdict"), "netSharpe": row.get("net_sharpe"),
            "beatsNull": row.get("beats_null_95"),
            "date": (row.get("run_at") or "")[:10]}


def _archive_row_external(row: dict) -> dict | None:
    if not row.get("repo"):
        return None
    return {"slug": Path(row.get("artifact") or "").stem,
            "source": row["repo"], "lane": "external",
            "status": row.get("verdict"), "netSharpe": None,
            "beatsNull": None, "date": (row.get("run_at") or "")[:10]}


def build_snapshot(root: Path) -> dict:
    articles = load_jsonl(root / "data" / "articles.jsonl")
    triage = load_jsonl(root / "data" / "triage.jsonl")
    lead = _leaderboard(root)
    external = load_jsonl(root / "results" / "external" / "leaderboard.jsonl")
    specs = sorted((root / "specs").glob("*.yaml")) if (root / "specs").exists() else []
    by_slug = {a.get("slug"): a for a in articles}

    archive = [r for r in (_archive_row_article(r, root) for r in lead) if r]
    archive += [r for r in (_archive_row_external(r) for r in external) if r]
    archive.sort(key=lambda r: r["date"], reverse=True)
    archive = archive[:MAX_ARCHIVE]

    chains = []
    for row in lead:
        slug = row.get("slug")
        if not slug or not (root / "reports" / f"{slug}.md").exists():
            continue
        article = by_slug.get(slug, {})
        spec_path = root / "specs" / f"{slug}.yaml"
        code_path = root / "strategies" / f"{slug}.py"
        report_path = root / "reports" / f"{slug}.md"
        chain = {"slug": slug, "title": article.get("title") or slug,
                 "stages": [
                     {"kind": "article", "title": article.get("title") or slug,
                      "body": truncate(article.get("blurb") or
                                       "(article not in cache)", MAX_BLURB),
                      "repoPath": f"data/articles.jsonl#{slug}"},
                     {"kind": "spec", "title": f"specs/{slug}.yaml",
                      "body": truncate(spec_path.read_text(errors="ignore")
                                       if spec_path.exists()
                                       else "(no spec yet)", MAX_ARTIFACT),
                      "repoPath": f"specs/{slug}.yaml"},
                     {"kind": "code", "title": f"strategies/{slug}.py",
                      "body": truncate(code_path.read_text(errors="ignore")
                                       if code_path.exists()
                                       else "(no generated code yet)",
                                       MAX_ARTIFACT),
                      "repoPath": f"strategies/{slug}.py"},
                     {"kind": "report", "title": f"reports/{slug}.md",
                      "body": truncate(report_path.read_text(errors="ignore"),
                                       MAX_ARTIFACT),
                      "repoPath": f"reports/{slug}.md"},
                 ]}
        chains.append(chain)
        if len(chains) >= MAX_CHAINS:
            break

    headline = None
    for row in reversed(lead):
        metrics = report_metrics(root / "reports" / f"{row.get('slug')}.md")
        if metrics:
            headline = {"slug": row["slug"], "metrics": metrics}
            break

    catalog_path = root / "data" / "catalog" / "index.json"
    providers: list[str] = []
    series = 0
    if catalog_path.exists():
        try:
            entries = json.loads(catalog_path.read_text()).get("series", [])
            series = len(entries)
            providers = sorted({e.get("id", "").split(":")[0]
                                for e in entries if e.get("id")})
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "counts": {"articles": len(articles), "triaged": len(triage),
                   "specs": len(specs), "backtests": len(lead),
                   "external": len(external)},
        "stages": [{"index": i, "name": n, "description": d, "artifact": a,
                    "doc": "https://github.com/uberdeveloper/autoquant#readme"}
                   for i, n, d, a in STAGES],
        "chains": chains,
        "archive": archive,
        "headline": headline,
        "catalog": {"series": series, "providers": providers},
    }


def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT), help="repo root to read")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args(argv)
    snap = build_snapshot(Path(args.root))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
    print(f"snapshot -> {out} ({sum(snap['counts'].values())} artifacts)")
    return 0


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_web_snapshot.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Generate the real snapshot and eyeball it**

Run: `uv run python scripts/web_snapshot.py`
Expected: `snapshot -> web/src/content/snapshot.json (N artifacts)` with N > 0

- [ ] **Step 6: Commit**

```bash
git add scripts/web_snapshot.py tests/test_web_snapshot.py
git commit -m "feat: web snapshot builder over real pipeline artifacts"
```

---

### Task 2: Scaffold the Vite app

**Files:**
- Create: `web/` (scaffold), `web/index.html`, `web/src/main.tsx`, `web/src/styles/tokens.css`, `web/vite.config.ts`, `web/.gitignore`

- [ ] **Step 1: Scaffold**

```bash
cd web 2>/dev/null || npm create vite@latest web -- --template react-ts
cd web && npm install
npm install react-router-dom lucide-react
npm install -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

Expected: `web/` with `package.json`, `src/`, no errors.

- [ ] **Step 2: Wire Tailwind v4 + Vitest** — replace `web/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    globals: true,
  },
});
```

Replace `web/tsconfig.json` `compilerOptions` additions (merge, don't drop):

```json
{ "compilerOptions": { "types": ["vitest/globals", "vite/client"] } }
```

- [ ] **Step 3: Design tokens** — create `web/src/styles/tokens.css`:

```css
@import "tailwindcss";

@theme {
  --color-bg: #0b0c0d;
  --color-surface: #131516;
  --color-ink: #f3f1ea;
  --color-dim: #969a97;
  --color-accent: #c5f467;
  --color-fail: #e5785c;
  --color-line: rgba(243, 241, 234, 0.13);
  --font-display: "Space Grotesk", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
}

html {
  background: var(--color-bg);
  color: var(--color-ink);
  scroll-behavior: smooth;
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  .reveal, .reveal * { transition: none !important; animation: none !important; opacity: 1 !important; transform: none !important; }
}

body {
  font-family: var(--font-display);
  -webkit-font-smoothing: antialiased;
}

/* thin grid-line motif for large sections */
.gridlines {
  background-image:
    linear-gradient(var(--color-line) 1px, transparent 1px);
  background-size: 100% 96px;
  opacity: 0.35;
}

/* scroll reveal */
.reveal { opacity: 0; transform: translateY(24px); transition: opacity 0.7s ease, transform 0.7s ease; }
.reveal.in { opacity: 1; transform: none; }

:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
```

- [ ] **Step 4: Fonts + root** — replace `web/index.html` `<head>`/`<body>`:

```html
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>AutoQuant — research the idea. test the evidence.</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300..700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
```

- [ ] **Step 5: App shell** — replace `web/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles/tokens.css";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import WorkspaceStub from "./sections/WorkspaceStub";

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<main>{/* sections land here (Task 6+) */}</main>} />
        <Route path="/workspace" element={<WorkspaceStub />} />
      </Routes>
      <Footer />
    </BrowserRouter>
  );
}
```

Delete the scaffold's `App.css` / `src/App.tsx` and its imports. Create a
minimal `web/src/components/Nav.tsx`, `Footer.tsx`, `sections/WorkspaceStub.tsx`
(placeholder `<header>` returns is fine — real versions in Tasks 4–5), and
verify the shell boots.

- [ ] **Step 6: Verify**

Run: `cd web && npm run build`
Expected: build succeeds; `npm run dev` serves a dark page at :5173.

- [ ] **Step 7: Commit**

```bash
cd .. && git add web && git commit -m "feat(web): vite+tailwind shell with design tokens"
```

---

### Task 3: Typed snapshot loader + empty fallback (TDD)

**Files:**
- Create: `web/src/content/snapshot.ts`, `web/tests/setup.ts`, `web/tests/snapshot.test.ts`

- [ ] **Step 1: Test setup** — create `web/tests/setup.ts`:

```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 2: Write the failing tests** — `web/tests/snapshot.test.ts`:

```ts
import { loadSnapshot, emptySnapshot, type Snapshot } from "../src/content/snapshot";

describe("loadSnapshot", () => {
  it("falls back to a valid empty snapshot when the file is missing", () => {
    const snap = loadSnapshot(undefined);
    expect(snap).toEqual(emptySnapshot());
    expect(snap.counts.articles).toBe(0);
    expect(snap.stages).toHaveLength(7);
  });

  it("accepts a parsed object with the contract shape", () => {
    const raw = { ...emptySnapshot(), generatedAt: "2026-10-20T00:00:00+00:00" };
    const snap = loadSnapshot(raw);
    expect(snap.generatedAt).toBe("2026-10-20T00:00:00+00:00");
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `cd web && npx vitest run tests/snapshot.test.ts`
Expected: FAIL — module not found

- [ ] **Step 4: Implement** — `web/src/content/snapshot.ts`:

```ts
/** Typed view of scripts/web_snapshot.py output. The loader never throws:
 * a missing or malformed snapshot degrades to a valid empty one so the
 * landing always renders (empty states, never fake content). */

export interface Counts { articles: number; triaged: number; specs: number; backtests: number; external: number; }
export interface Stage { index: string; name: string; description: string; artifact: string; doc: string; }
export interface ChainStage { kind: "article" | "spec" | "code" | "report"; title: string; body: string; repoPath: string; }
export interface Chain { slug: string; title: string; stages: ChainStage[]; }
export interface ArchiveRow { slug: string; source: string; lane: "article" | "external"; status: string | null; netSharpe: number | null; beatsNull: boolean | null; date: string; }
export interface Headline { slug: string; metrics: { label: string; strategy: string; benchmark: string }[]; }
export interface CatalogInfo { series: number; providers: string[]; }
export interface Snapshot { generatedAt: string; counts: Counts; stages: Stage[]; chains: Chain[]; archive: ArchiveRow[]; headline: Headline | null; catalog: CatalogInfo; }

export const emptySnapshot = (): Snapshot => ({
  generatedAt: "",
  counts: { articles: 0, triaged: 0, specs: 0, backtests: 0, external: 0 },
  stages: [],
  chains: [],
  archive: [],
  headline: null,
  catalog: { series: 0, providers: [] },
});

export function loadSnapshot(raw: unknown): Snapshot {
  if (!raw || typeof raw !== "object") return emptySnapshot();
  const s = raw as Partial<Snapshot>;
  return {
    generatedAt: s.generatedAt ?? "",
    counts: { ...emptySnapshot().counts, ...s.counts },
    stages: Array.isArray(s.stages) ? s.stages : [],
    chains: Array.isArray(s.chains) ? s.chains : [],
    archive: Array.isArray(s.archive) ? s.archive : [],
    headline: s.headline ?? null,
    catalog: s.catalog ?? { series: 0, providers: [] },
  };
}

/** Vite static import of the generated JSON. Run scripts/web_snapshot.py first. */
import generated from "./snapshot.json";
export const snapshot: Snapshot = loadSnapshot(generated);
```

Note: `snapshot.json` must exist for the import to type-check — generate it
(`uv run python scripts/web_snapshot.py`) before building. Add a `.gitignore`
entry: `web/src/content/snapshot.json`.

- [ ] **Step 5: Verify**

Run: `cd web && npx vitest run tests/snapshot.test.ts`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add web/src/content/snapshot.ts web/tests && git commit -m "feat(web): typed snapshot loader with empty fallback"
```

---

### Task 4: Primitives — StatusDot, MetricReadout, Reveal (TDD)

**Files:**
- Create: `web/src/components/StatusDot.tsx`, `MetricReadout.tsx`, `Reveal.tsx`, `web/src/lib/reveal.ts`, `web/tests/sections.test.tsx`

- [ ] **Step 1: Write the failing tests** (append to `web/tests/sections.test.tsx`):

```tsx
import { render, screen } from "@testing-library/react";
import { StatusDot } from "../src/components/StatusDot";
import { MetricReadout } from "../src/components/MetricReadout";

describe("StatusDot", () => {
  it("maps ok-like verdicts to the accent", () => {
    const { container } = render(<StatusDot verdict="ok" />);
    expect(container.firstChild).toHaveClass("bg-accent");
  });
  it("maps error verdicts to fail color", () => {
    const { container } = render(<StatusDot verdict="error" />);
    expect(container.firstChild).toHaveClass("bg-fail");
  });
  it("maps everything else to dim", () => {
    const { container } = render(<StatusDot verdict="PENDING" />);
    expect(container.firstChild).toHaveClass("bg-dim");
  });
});

describe("MetricReadout", () => {
  it("renders label and value in mono", () => {
    render(<MetricReadout label="SHARPE" value="-0.04" />);
    expect(screen.getByText("SHARPE")).toBeInTheDocument();
    expect(screen.getByText("-0.04")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Verify failure** — `cd web && npx vitest run tests/sections.test.tsx`
Expected: FAIL — modules not found

- [ ] **Step 3: Implement**

`web/src/lib/reveal.ts`:

```ts
import { useEffect, useRef } from "react";

/** Adds .in to .reveal elements when they enter the viewport. One global
 * observer; reduced-motion users get .in immediately via CSS override. */
export function useRevealRoot() {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
      { threshold: 0.15 },
    );
    root.querySelectorAll(".reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}
```

`web/src/components/Reveal.tsx`:

```tsx
import type { ReactNode } from "react";

export function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`reveal ${className}`}>{children}</div>;
}
```

`web/src/components/StatusDot.tsx`:

```tsx
const OK = new Set(["ok", "PASS", "CODED"]);
const FAIL = new Set(["error", "timeout", "FAIL"]);

export function StatusDot({ verdict, label }: { verdict: string | null; label?: string }) {
  const v = (verdict ?? "").toLowerCase();
  const cls = OK.has(verdict ?? "") || OK.has(v) ? "bg-accent"
    : FAIL.has(v) ? "bg-fail" : "bg-dim";
  return (
    <span className="inline-flex items-center gap-2" aria-label={`status ${verdict ?? "unknown"}`}>
      <span aria-hidden className={`inline-block h-1.5 w-1.5 rounded-full ${cls}`} />
      {label && <span className="font-mono text-xs text-dim">{label}</span>}
    </span>
  );
}
```

`web/src/components/MetricReadout.tsx`:

```tsx
export function MetricReadout({ label, value, big = false }: { label: string; value: string; big?: boolean }) {
  return (
    <div>
      <div className="font-mono text-[11px] uppercase tracking-widest text-dim">{label}</div>
      <div className={`font-mono tabular-nums ${big ? "text-5xl" : "text-2xl"} text-ink`}>{value}</div>
    </div>
  );
}
```

- [ ] **Step 4: Verify** — `cd web && npx vitest run tests/sections.test.tsx` → PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add web/src web/tests && git commit -m "feat(web): status dot, metric readout, reveal primitives"
```

---

### Task 5: Nav, Footer, WorkspaceStub

**Files:**
- Modify: `web/src/components/Nav.tsx`, `web/src/components/Footer.tsx`, `web/src/sections/WorkspaceStub.tsx`, `web/src/main.tsx`

- [ ] **Step 1: Nav** — replace `web/src/components/Nav.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Menu, X } from "lucide-react";

const LINKS = [
  ["Product", "#product"],
  ["Pipeline", "#pipeline"],
  ["Experiments", "#experiments"],
  ["Documentation", "https://github.com/uberdeveloper/autoquant#readme"],
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`fixed inset-x-0 top-0 z-50 border-b transition-colors
      ${scrolled ? "border-line bg-bg/85 backdrop-blur" : "border-transparent"}`}>
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4"
           aria-label="Main">
        <Link to="/" className="font-mono text-sm font-medium tracking-[0.3em]">
          AUTOQUANT
        </Link>
        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map(([label, href]) => (
            <a key={label} href={href} className="text-sm text-dim transition-colors hover:text-ink">
              {label}
            </a>
          ))}
          <Link to="/workspace"
                className="border border-line px-4 py-2 font-mono text-xs tracking-widest text-accent transition-colors hover:border-accent">
            OPEN WORKSPACE <ArrowUpRight className="ml-1 inline h-3 w-3" />
          </Link>
        </div>
        <button className="md:hidden" aria-label="Menu"
                onClick={() => setOpen(!open)}>
          {open ? <X /> : <Menu />}
        </button>
      </nav>
      {open && (
        <div className="border-t border-line bg-bg px-6 py-8 md:hidden">
          {LINKS.map(([label, href]) => (
            <a key={label} href={href} onClick={() => setOpen(false)}
               className="block py-3 text-2xl text-ink">{label}</a>
          ))}
          <Link to="/workspace" onClick={() => setOpen(false)}
                className="mt-4 block font-mono text-sm text-accent">OPEN WORKSPACE →</Link>
        </div>
      )}
    </header>
  );
}
```

- [ ] **Step 2: Footer** — replace `web/src/components/Footer.tsx`:

```tsx
export default function Footer() {
  return (
    <footer className="border-t border-line px-6 py-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="font-mono text-sm tracking-[0.3em]">AUTOQUANT</div>
          <p className="mt-3 max-w-md text-sm text-dim">
            Historical backtests are research evidence, not guarantees of
            future performance. Every number on this site is reproducible
            from the repository.
          </p>
        </div>
        <div className="font-mono text-xs text-dim">
          harvest → fetch → triage → spec → codegen → backtest → leaderboard
        </div>
      </div>
    </footer>
  );
}
```

- [ ] **Step 3: WorkspaceStub** — replace `web/src/sections/WorkspaceStub.tsx`:

```tsx
import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function WorkspaceStub() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6">
      <div className="font-mono text-xs tracking-widest text-dim">/WORKSPACE</div>
      <h1 className="mt-4 text-5xl font-light leading-tight">
        The research terminal is under construction.
      </h1>
      <p className="mt-6 max-w-xl text-dim">
        The workspace screens (research feed, triage, strategy lab, backtest
        explorer, leaderboard) are the next build slice. Today you can inspect
        every artifact directly in the repository: reports live in{" "}
        <code className="font-mono text-ink">reports/</code>, the leaderboard
        in <code className="font-mono text-ink">results/leaderboard.jsonl</code>,
        and strategy specs in <code className="font-mono text-ink">specs/</code>.
      </p>
      <Link to="/" className="mt-8 inline-flex w-fit items-center gap-2 font-mono text-sm text-accent">
        <ArrowLeft className="h-4 w-4" /> Back to the landing
      </Link>
    </main>
  );
}
```

- [ ] **Step 4: Verify** — `cd web && npm run build` → success; `/workspace` renders the stub.

- [ ] **Step 5: Commit**

```bash
git add web/src && git commit -m "feat(web): nav, footer, honest workspace stub"
```

---

### Task 6: Hero

**Files:**
- Create: `web/src/sections/Hero.tsx`
- Modify: `web/src/main.tsx` (mount `<Hero />` + `useRevealRoot` on `/`)

- [ ] **Step 1: Implement** — `web/src/sections/Hero.tsx`:

```tsx
import { Link } from "react-router-dom";
import { ArrowDown } from "lucide-react";
import { snapshot } from "../content/snapshot";

const YAML_LINES = [
  "meta:", "  slug: spy-200dma-timing", "signal:",
  "  definition: close > sma200", "rules:",
  "  entry: cross_above", "  execution_price: next_open",
];
const PROSE =
  "Holding an index only while it trades above its 200-day average has " +
 "historically improved risk-adjusted returns.";

export default function Hero() {
  const n = Object.values(snapshot.counts).reduce((a, b) => a + b, 0);
  return (
    <section className="relative overflow-hidden px-6 pb-24 pt-40 md:pt-48" id="product">
      <div className="gridlines pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto grid max-w-6xl gap-16 md:grid-cols-[1.2fr_1fr] md:items-center">
        <div>
          <div className="mb-8 inline-flex items-center gap-2 border border-line px-3 py-1.5 font-mono text-[11px] tracking-widest text-dim">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            PIPELINE IDLE — {n} ARTIFACTS INDEXED
          </div>
          <h1 className="text-5xl font-light leading-[1.05] md:text-7xl">
            Research the idea.
            <br />
            <span className="text-dim">Test the evidence.</span>
          </h1>
          <p className="mt-8 max-w-md text-lg leading-relaxed text-dim">
            Turn quantitative research into explicit trading hypotheses,
            reproducible backtests, and evidence you can inspect.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link to="/workspace"
                  className="bg-accent px-6 py-3 font-mono text-xs font-medium tracking-widest text-bg transition-opacity hover:opacity-85">
              EXPLORE THE WORKSPACE
            </Link>
            <a href="#pipeline"
               className="border border-line px-6 py-3 font-mono text-xs tracking-widest text-ink transition-colors hover:border-accent">
              UNDERSTAND THE PIPELINE
            </a>
          </div>
        </div>

        {/* prose -> yaml -> equity trace */}
        <div className="hidden border border-line bg-surface/50 p-6 md:block" aria-hidden>
          <div className="space-y-1 text-sm leading-relaxed text-dim [mask-image:linear-gradient(180deg,ink,transparent)]">
            <p className="prose-fade">{PROSE}</p>
          </div>
          <div className="mt-6 font-mono text-xs leading-relaxed text-accent/80">
            {YAML_LINES.map((l, i) => (
              <div key={i} className="yaml-line" style={{ animationDelay: `${0.9 + i * 0.18}s` }}>
                {l}
              </div>
            ))}
          </div>
          <svg viewBox="0 0 300 80" className="mt-6 w-full">
            <path d="M0,60 L30,55 L60,58 L90,44 L120,48 L150,36 L180,40 L210,28 L240,32 L270,20 L300,24"
                  fill="none" stroke="var(--color-accent)" strokeWidth="1.5"
                  className="curve-draw" style={{ animationDelay: "2.6s" }} />
          </svg>
          <div className="curve-readout mt-3 flex justify-between font-mono text-xs text-dim" style={{ animationDelay: "3.8s" }}>
            <span>SHARPE 1.06</span><span>MAXDD -18%</span><span>62 TRADES</span>
          </div>
          <p className="mt-3 font-mono text-[10px] text-dim/60">
            illustration of the pipeline — live numbers come from real reports below
          </p>
        </div>
      </div>
      <a href="#pipeline" aria-label="Scroll to pipeline"
         className="absolute bottom-8 left-1/2 -translate-x-1/2 text-dim">
        <ArrowDown className="h-4 w-4 animate-bounce" />
      </a>
    </section>
  );
}
```

Append the keyframes to `web/src/styles/tokens.css`:

```css
@keyframes fadeUp { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
.prose-fade { animation: fadeUp 1.2s ease both; }
.yaml-line { opacity: 0; animation: fadeUp 0.5s ease both; }
@keyframes draw { from { stroke-dashoffset: 600; } to { stroke-dashoffset: 0; } }
.curve-draw { stroke-dasharray: 600; opacity: 0; animation: draw 1.6s ease forwards, fadeUp 0.3s ease forwards; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
.curve-readout { opacity: 0; animation: fadeIn 0.6s ease both; }
@media (prefers-reduced-motion: reduce) {
  .yaml-line, .curve-draw, .curve-readout, .prose-fade { animation: none; opacity: 1; stroke-dashoffset: 0; }
}
```

Note: the illustration numbers (SHARPE 1.06…) are explicitly labelled as an
illustration in the caption — real numbers only appear in Evidence/Archive,
which read the snapshot. This is the one place a number isn't live, and the
caption says so.

- [ ] **Step 2: Mount** — in `main.tsx`, the `/` route becomes:

```tsx
<Route path="/" element={<Landing />} />
```

with a new `Landing` component in `main.tsx` that wraps the sections and calls
`useRevealRoot()`:

```tsx
function Landing() {
  const ref = useRevealRoot();
  return (
    <main ref={ref}>
      <Hero />
      {/* Pipeline, InMotion, Evidence, Archive, FinalCta land in Tasks 7-10 */}
    </main>
  );
}
```

- [ ] **Step 3: Verify** — `npm run build` passes; visually check :5173 (headline scale, animation timing, reduced-motion).

- [ ] **Step 4: Commit**

```bash
git add web/src && git commit -m "feat(web): hero with pipeline illustration animation"
```

---

### Task 7: Pipeline section (01–07)

**Files:**
- Create: `web/src/sections/Pipeline.tsx`; modify `main.tsx`

- [ ] **Step 1: Implement** — `web/src/sections/Pipeline.tsx`:

```tsx
import { Reveal } from "../components/Reveal";
import { snapshot } from "../content/snapshot";

export default function Pipeline() {
  return (
    <section id="pipeline" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal>
        <p className="font-mono text-xs tracking-widest text-dim">THE PIPELINE</p>
        <h2 className="mt-4 max-w-2xl text-4xl font-light md:text-6xl">
          From idea to evidence,
          <br />
          <span className="text-dim">seven honest stages.</span>
        </h2>
      </Reveal>
      <ol className="mt-20 border-t border-line">
        {snapshot.stages.map((s) => (
          <Reveal key={s.index}>
            <li className="group relative border-b border-line py-8 transition-colors hover:bg-surface/60">
              <a href={s.doc} className="mx-auto grid max-w-6xl grid-cols-[auto_1fr] items-baseline gap-6 px-2 md:grid-cols-[80px_1fr_auto]">
                <span className="font-mono text-sm text-dim transition-colors group-hover:text-accent">
                  {s.index}
                </span>
                <div>
                  <h3 className="text-2xl font-light">{s.name}</h3>
                  <p className="mt-1 max-w-xl text-sm text-dim">{s.description}</p>
                </div>
                <span className="hidden font-mono text-xs text-dim/70 md:block">
                  {s.artifact}
                </span>
              </a>
            </li>
          </Reveal>
        ))}
      </ol>
    </section>
  );
}
```

- [ ] **Step 2: Mount inside `Landing`** after `<Hero />`.
- [ ] **Step 3: Verify** — build passes; rows reveal on scroll; hover tint works.
- [ ] **Step 4: Commit** — `git commit -am "feat(web): pipeline stage rows"`

---

### Task 8: Research in motion (artifact chain)

**Files:**
- Create: `web/src/sections/InMotion.tsx`; modify `main.tsx`

- [ ] **Step 1: Implement** — `web/src/sections/InMotion.tsx`:

```tsx
import { useState } from "react";
import { Reveal } from "../components/Reveal";
import { snapshot } from "../content/snapshot";

const KINDS = ["article", "spec", "code", "report"] as const;
type Kind = (typeof KINDS)[number];

const LABEL: Record<Kind, string> = {
  article: "01 · SOURCE ARTICLE",
  spec: "02 · STRATEGY SPEC",
  code: "03 · GENERATED CODE",
  report: "04 · BACKTEST REPORT",
};

export default function InMotion() {
  const [step, setStep] = useState(0);
  const chain = snapshot.chains[0];
  if (!chain) {
    return (
      <section id="motion" className="border-y border-line px-6 py-32">
        <div className="mx-auto max-w-6xl">
          <p className="font-mono text-xs tracking-widest text-dim">RESEARCH IN MOTION</p>
          <p className="mt-6 max-w-xl text-dim">
            No completed experiment chains yet — run the pipeline and re-generate
            the snapshot (`uv run python scripts/web_snapshot.py`).
          </p>
        </div>
      </section>
    );
  }
  const stage = chain.stages[step];
  return (
    <section id="motion" className="border-y border-line bg-surface/30 px-6 py-32">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="font-mono text-xs tracking-widest text-dim">RESEARCH IN MOTION</p>
          <h2 className="mt-4 max-w-2xl text-4xl font-light md:text-5xl">{chain.title}</h2>
        </Reveal>
        <div role="tablist" aria-label="Artifact stages" className="mt-12 flex flex-wrap gap-2">
          {chain.stages.map((s, i) => (
            <button key={s.kind} role="tab" aria-selected={i === step}
                    onClick={() => setStep(i)}
                    className={`border px-4 py-2 font-mono text-[11px] tracking-widest transition-colors
                      ${i === step ? "border-accent text-accent" : "border-line text-dim hover:text-ink"}`}>
              {LABEL[s.kind as Kind]}
            </button>
          ))}
        </div>
        <div className="mt-6 border border-line bg-bg">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <span className="font-mono text-xs text-dim">{stage.title}</span>
            <a href={`https://github.com/uberdeveloper/autoquant/blob/main/${stage.repoPath}`}
               className="font-mono text-[11px] text-dim hover:text-accent">
              inspect in repo →
            </a>
          </div>
          <pre className="max-h-[28rem] overflow-auto p-6 font-mono text-xs leading-relaxed text-ink/90">
            {stage.body}
          </pre>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Mount** after `<Pipeline />`.
- [ ] **Step 3: Verify** — build passes; tabs switch panels; chain content matches the real coherence experiment in the repo.
- [ ] **Step 4: Commit** — `git commit -am "feat(web): research-in-motion artifact chain"`

---

### Task 9: Evidence + Archive

**Files:**
- Create: `web/src/sections/Evidence.tsx`, `web/src/sections/Archive.tsx`; modify `main.tsx`

- [ ] **Step 1: Evidence** — `web/src/sections/Evidence.tsx`:

```tsx
import { Reveal } from "../components/Reveal";
import { MetricReadout } from "../components/MetricReadout";
import { snapshot } from "../content/snapshot";

export default function Evidence() {
  const h = snapshot.headline;
  return (
    <section id="evidence" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal>
        <h2 className="max-w-3xl text-4xl font-light leading-tight md:text-6xl">
          Evidence over assumptions.
        </h2>
        <p className="mt-6 max-w-xl text-dim">
          Every strategy survives the same gauntlet: explicit rules, real
          price history, explicit costs, and a null model. Historical
          backtests are research evidence, not guarantees.
        </p>
      </Reveal>
      {h ? (
        <Reveal className="mt-16">
          <div className="border border-line bg-surface/50 p-8">
            <div className="font-mono text-xs tracking-widest text-dim">
              LATEST RUN — {h.slug}
            </div>
            <div className="mt-8 grid grid-cols-2 gap-8 md:grid-cols-4">
              {h.metrics.slice(0, 8).map((m) => (
                <MetricReadout key={m.label} label={m.label}
                               value={m.strategy} />
              ))}
            </div>
            <p className="mt-8 font-mono text-[11px] text-dim">
              strategy column, net of costs — full tables in reports/{h.slug}.md
            </p>
          </div>
        </Reveal>
      ) : (
        <Reveal className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          No completed backtest runs yet — the evidence panel fills in from
          reports/ once the pipeline has run.
        </Reveal>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Archive** — `web/src/sections/Archive.tsx`:

```tsx
import { useState } from "react";
import { Reveal } from "../components/Reveal";
import { StatusDot } from "../components/StatusDot";
import { snapshot } from "../content/snapshot";

type SortKey = "date" | "sharpe";
const fmt = (n: number | null) =>
  n === null || n === undefined ? "—" : n.toFixed(2);

export default function Archive() {
  const [sort, setSort] = useState<SortKey>("date");
  const rows = [...snapshot.archive].sort((a, b) =>
    sort === "date" ? b.date.localeCompare(a.date)
                    : (b.netSharpe ?? -99) - (a.netSharpe ?? -99));

  return (
    <section id="experiments" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="font-mono text-xs tracking-widest text-dim">THE EXPERIMENT ARCHIVE</p>
          <h2 className="mt-4 text-4xl font-light md:text-6xl">
            Every test, <span className="text-dim">on the record.</span>
          </h2>
        </div>
        <label className="font-mono text-xs text-dim">
          RANK BY{" "}
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}
                  className="ml-2 border border-line bg-bg px-3 py-2 font-mono text-xs text-ink">
            <option value="date">RUN DATE</option>
            <option value="sharpe">NET SHARPE</option>
          </select>
        </label>
      </Reveal>

      {rows.length === 0 ? (
        <Reveal className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          No experiments on the leaderboard yet.
        </Reveal>
      ) : (
        <ol className="mt-16 border-t border-line">
          {rows.map((r) => (
            <Reveal key={`${r.lane}-${r.slug}`}>
              <li className="grid grid-cols-[auto_1fr_auto] items-center gap-6 border-b border-line py-5 transition-colors hover:bg-surface/60">
                <StatusDot verdict={r.status} />
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm text-ink">{r.slug}</div>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-dim">
                    {r.source} · {r.date}
                  </div>
                </div>
                <div className="text-right font-mono text-sm tabular-nums">
                  {fmt(r.netSharpe)}
                  <div className="font-mono text-[10px] text-dim">NET SHARPE</div>
                </div>
              </li>
            </Reveal>
          ))}
        </ol>
      )}
      <p className="mt-6 font-mono text-[11px] text-dim">
        Historical performance is not indicative of future results.
      </p>
    </section>
  );
}
```

- [ ] **Step 3: Mount** both after `<InMotion />`.
- [ ] **Step 4: Verify** — build passes; sort re-orders; empty states render when the snapshot is empty.
- [ ] **Step 5: Commit** — `git commit -am "feat(web): evidence panel and experiment archive"`

---

### Task 10: Final CTA

**Files:**
- Create: `web/src/sections/FinalCta.tsx`; modify `main.tsx`

- [ ] **Step 1: Implement** — `web/src/sections/FinalCta.tsx`:

```tsx
import { Link } from "react-router-dom";

export default function FinalCta() {
  return (
    <section className="relative overflow-hidden border-t border-line px-6 py-40 text-center">
      <div className="gridlines pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto max-w-3xl">
        <h2 className="text-4xl font-light leading-tight md:text-6xl">
          Good research starts with<br />
          <span className="text-dim">a testable question.</span>
        </h2>
        <Link to="/workspace"
              className="mt-12 inline-block bg-accent px-8 py-4 font-mono text-xs font-medium tracking-widest text-bg transition-opacity hover:opacity-85">
          OPEN THE WORKSPACE
        </Link>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Mount** after `<Archive />` in `Landing`.
- [ ] **Step 3: Verify + commit** — build passes; `git commit -am "feat(web): final CTA"`

---

### Task 11: Component tests

**Files:**
- Modify: `web/tests/sections.test.tsx`

- [ ] **Step 1: Write the tests** (append):

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Archive } from "../src/sections/Archive";
import { Evidence } from "../src/sections/Evidence";
import { Pipeline } from "../src/sections/Pipeline";
import InMotion from "../src/sections/InMotion";
import { emptySnapshot } from "../src/content/snapshot";
import * as snapmod from "../src/content/snapshot";

const withSnap = (ui: React.ReactElement, snap: Partial<snapmod.Snapshot>) => {
  jest.spyOn(snapmod, "snapshot", "get").mockReturnValue(
    snapmod.loadSnapshot({ ...snapmod.emptySnapshot(), ...snap }));
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};
```

Because `sections` import the const `snapshot` directly, prefer module-level
mocking instead — at the top of the file:

```tsx
const MOCK: snapmod.Snapshot = snapmod.loadSnapshot({
  stages: [{ index: "01", name: "Discover research", description: "d",
             artifact: "data/articles.jsonl", doc: "#" }],
  chains: [{ slug: "a", title: "A chain", stages: [
    { kind: "article", title: "a.md", body: "prose", repoPath: "p" },
    { kind: "spec", title: "s.yaml", body: "meta:", repoPath: "p" }] }],
  archive: [
    { slug: "s1", source: "src", lane: "article", status: "PENDING",
      netSharpe: 1.5, beatsNull: true, date: "2026-02-01" },
    { slug: "s2", source: "o/r", lane: "external", status: "ok",
      netSharpe: null, beatsNull: null, date: "2026-03-01" },
  ],
  headline: { slug: "s1", metrics: [{ label: "Sharpe", strategy: "-0.04", benchmark: "0.46" }] },
});

vi.mock("../src/content/snapshot", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../src/content/snapshot")>();
  return { ...orig, snapshot: MOCK };
});

describe("Archive", () => {
  it("renders rows and sorts by sharpe", async () => {
    render(<MemoryRouter><Archive /></MemoryRouter>);
    expect(screen.getByText("s1")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
    const first = screen.getAllByText(/NET SHARPE/)[0].closest("li")!;
    expect(first).toHaveTextContent("s1");
  });
  it("shows an empty state with no experiments", () => {
    vi.mocked(snapmod).archive = []; // not needed if MOCK covers; assert via separate mock below
  });
});
```

(Implement the empty-state case with a second `vi.mock` factory in a sibling
test file or by exporting `Archive` to accept optional rows prop — choose the
props approach: `Archive({ rows }: { rows?: ArchiveRow[] })` defaulting to
`snapshot.archive`, which keeps the component pure and testable. Same for
`Evidence({ headline }: ...)` and `InMotion({ chain }: ...)`.)

```tsx
describe("Evidence", () => {
  it("renders real metrics and the disclaimer position", () => {
    render(<Evidence headline={MOCK.headline} />);
    expect(screen.getByText("-0.04")).toBeInTheDocument();
  });
  it("renders the empty state without a headline", () => {
    render(<Evidence headline={null} />);
    expect(screen.getByText(/No completed backtest runs yet/i)).toBeInTheDocument();
  });
});

describe("InMotion", () => {
  it("switches artifact panels via tabs", async () => {
    render(<InMotion chain={MOCK.chains[0]} />);
    expect(screen.getByText("prose")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /SPEC/ }));
    expect(screen.getByText("meta:")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Adjust components to accept props** — each section takes the
  slice as an optional prop defaulting to the snapshot value (as noted above).
  Update the `main.tsx` mount sites accordingly (no props passed there).

- [ ] **Step 3: Run** — `cd web && npx vitest run` → all PASS.

- [ ] **Step 4: Commit** — `git add web && git commit -m "test(web): section components"`

---

### Task 12: README + full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: README section** — add after the running-the-pipeline docs:

```markdown
## Web frontend (landing)

The landing page renders a build-time snapshot of the real pipeline
artifacts — no runtime backend, no fabricated content.

    uv run python scripts/web_snapshot.py   # regenerate snapshot from artifacts
    cd web && npm install                   # once
    cd web && npm run dev                   # http://localhost:5173
    cd web && npm run build && npm run preview   # production build

Re-run the snapshot script whenever pipeline artifacts change; the landing
shows empty states on a fresh install by design.
```

- [ ] **Step 2: Full verification**

```bash
cd web && npm run build && npx vitest run
cd .. && uv run python -m pytest
```

Expected: build clean, all Vitest tests pass, all Python tests pass
(375 existing + 7 snapshot tests).

- [ ] **Step 3: Manual smoke**

`npm run dev` → check hero animation, pipeline reveals, chain tabs, archive
sort, mobile nav at 390px, keyboard tab-through, and reduced-motion (devtools
emulation).

- [ ] **Step 4: Commit**

```bash
git add README.md && git commit -m "docs: web frontend setup and snapshot workflow"
```

---

## Self-review notes

- Spec coverage: snapshot script (Task 1), loader+fallback (Task 3), tokens &
  primitives (Tasks 2, 4), nav/footer/stub (Task 5), hero (6), pipeline (7),
  in-motion (8), evidence+archive (9), final CTA (10), tests (11), README +
  gates (12). A11y/reduced-motion handled in tokens.css + Reveal + tablist ARIA.
- Type consistency: `Snapshot`/`Chain`/`ArchiveRow` shapes identical between
  the Python builder and `snapshot.ts`; section props match Task 11 usage.
- Deviation worth noting: sections take optional props (defaulting to the
  snapshot const) so they are unit-testable without module mocks.
