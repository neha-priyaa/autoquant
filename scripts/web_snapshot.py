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

ROOT = Path(__file__).resolve().parent.parent
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
    if len(text) <= limit:
        return text
    return text[:limit - 2].rsplit(" ", 1)[0] + " …"


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
    lead = load_jsonl(root / "results" / "leaderboard.jsonl")
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
        chains.append({
            "slug": slug, "title": article.get("title") or slug,
            "stages": [
                {"kind": "article", "title": article.get("title") or slug,
                 "body": truncate(article.get("blurb") or
                                  "(article not in cache)", MAX_BLURB),
                 "repoPath": f"data/articles.jsonl#{slug}"},
                {"kind": "spec", "title": f"specs/{slug}.yaml",
                 "body": truncate(spec_path.read_text(errors="ignore")
                                  if spec_path.exists() else "(no spec yet)",
                                  MAX_ARTIFACT),
                 "repoPath": f"specs/{slug}.yaml"},
                {"kind": "code", "title": f"strategies/{slug}.py",
                 "body": truncate(code_path.read_text(errors="ignore")
                                  if code_path.exists()
                                  else "(no generated code yet)", MAX_ARTIFACT),
                 "repoPath": f"strategies/{slug}.py"},
                {"kind": "report", "title": f"reports/{slug}.md",
                 "body": truncate(report_path.read_text(errors="ignore"),
                                  MAX_ARTIFACT),
                 "repoPath": f"reports/{slug}.md"},
            ]})
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
