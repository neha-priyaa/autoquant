"""Contract tests for scripts/web_snapshot.py — builds snapshot JSON from
real artifacts; must tolerate a fresh install with no artifacts at all."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location(
        "web_snapshot", ROOT / "scripts" / "web_snapshot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestEmptyInstall:
    def test_missing_everything_yields_valid_empty_snapshot(self, tmp_path):
        ws = load_module()
        snap = ws.build_snapshot(tmp_path)
        assert snap["counts"] == {"articles": 0, "triaged": 0, "specs": 0,
                                  "backtests": 0, "external": 0}
        assert snap["chains"] == [] and snap["archive"] == []
        assert snap["headline"] is None
        assert snap["catalog"] == {"series": 0, "providers": []}
        assert len(snap["stages"]) == 7
        assert snap["generatedAt"]

    def test_stages_describe_real_artifacts(self, tmp_path):
        ws = load_module()
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
        ws = load_module()
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
        ws = load_module()
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
        ws = load_module()
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
        ws = load_module()
        snap = ws.build_snapshot(tmp_path)
        chain = snap["chains"][0]
        kinds = [s["kind"] for s in chain["stages"]]
        assert kinds == ["article", "spec", "code", "report"]
        assert len(chain["stages"][0]["body"]) <= 400
        assert len(chain["stages"][1]["body"]) <= 1200
        assert len(chain["stages"][2]["body"]) <= 1200

    def test_cli_writes_file(self, tmp_path):
        ws = load_module()
        out = tmp_path / "out" / "snapshot.json"
        rc = ws.main_with(["--root", str(tmp_path), "--out", str(out)])
        assert rc == 0 and json.loads(out.read_text())["generatedAt"]


class TestWorkspace:
    def test_workspace_sections_present_even_when_empty(self, tmp_path):
        ws = load_module()
        w = ws.build_snapshot(tmp_path)["workspace"]
        assert w["articles"] == [] and w["triage"] == []
        assert w["specs"] == [] and w["runs"] == []
        assert w["reports"] == {} and w["failed"] == [] and w["catalog"] == []

    def test_articles_and_triage_rows(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "articles.jsonl").write_text(json.dumps({
            "slug": "a", "title": "A", "url": "https://x", "source": "S",
            "posted": "2026-01-01", "blurb": "b", "stage": "fetched",
            "triage_score": 7}) + "\n")
        (tmp_path / "data" / "triage.jsonl").write_text(json.dumps({
            "slug": "a", "title": "A", "url": "https://x", "score": 7,
            "claim": "c", "asset_class": "equity", "red_flags": ["r1"],
            "missing": ["m1"], "reason": "why"}) + "\n")
        w = load_module().build_snapshot(tmp_path)["workspace"]
        assert w["articles"][0]["triageScore"] == 7
        t = w["triage"][0]
        assert t["assetClass"] == "equity" and t["redFlags"] == ["r1"]

    def test_specs_structured_fields(self, tmp_path):
        (tmp_path / "specs").mkdir()
        (tmp_path / "specs" / "a.yaml").write_text(
            "meta:\n  slug: a\n  title: A\n"
            "data:\n  universe: [SPY, TLT]\n  bar: 1d\n"
            "signal:\n  definition: close > sma200\n"
            "rules:\n  entry: cross_above\n  exit: cross_below\n"
            "  direction: long_only\n"
            "verdict:\n  status: PENDING\n")
        (tmp_path / "strategies").mkdir()
        (tmp_path / "strategies" / "a.py").write_text("import pandas\n")
        w = load_module().build_snapshot(tmp_path)["workspace"]
        s = w["specs"][0]
        assert s["universe"] == ["SPY", "TLT"] and s["hasCode"] is True
        assert s["entry"] == "cross_above" and s["status"] == "PENDING"
        assert "sma200" in s["signal"]

    def test_runs_include_flags_and_errors(self, tmp_path):
        (tmp_path / "results" / "external").mkdir(parents=True)
        (tmp_path / "results" / "leaderboard.jsonl").write_text(json.dumps({
            "slug": "a", "verdict": "PENDING", "net_sharpe": 1.0,
            "beats_null_95": True, "run_at": "2026-02-01T00:00:00",
            "flags": ["WEAK: x"]}) + "\n")
        (tmp_path / "results" / "external" / "leaderboard.jsonl").write_text(
            json.dumps({"repo": "o/r", "artifact": "n.ipynb", "kind": "notebook",
                        "verdict": "error", "error": "boom",
                        "run_at": "2026-03-01T00:00:00Z"}) + "\n")
        w = load_module().build_snapshot(tmp_path)["workspace"]
        assert w["runs"][0]["flags"] == ["WEAK: x"]
        assert w["runs"][1]["error"] == "boom"

    def test_reports_and_failed(self, tmp_path):
        (tmp_path / "results").mkdir()
        (tmp_path / "reports").mkdir()
        (tmp_path / "results" / "leaderboard.jsonl").write_text(json.dumps({
            "slug": "a", "verdict": "PENDING", "net_sharpe": -0.04,
            "beats_null_95": False, "run_at": "2026-02-01T00:00:00"}) + "\n")
        (tmp_path / "reports" / "a.md").write_text(
            "## Headline (net of costs)\n\n| | strategy | buy & hold |\n"
            "|---|---|---|\n| Sharpe | -0.04 | 0.46 |\n\nBody text here.\n")
        (tmp_path / "results" / "failed.jsonl").write_text(json.dumps({
            "spec": "/x/specs/b.yaml", "error": "exit 1: something broke"}) + "\n")
        w = load_module().build_snapshot(tmp_path)["workspace"]
        r = w["reports"]["a"]
        assert r["metrics"][0]["label"] == "Sharpe" and "Body text" in r["text"]
        assert w["failed"][0]["slug"] == "b" and "exit 1" in w["failed"][0]["error"]

    def test_catalog_from_repo_root_json(self, tmp_path):
        (tmp_path / "catalog.json").write_text(json.dumps({"version": 1, "series": [
            {"id": "yahoo:SPY", "title": "S&P 500 ETF (SPY)", "tags": ["equity"],
             "frequency": "daily", "coverage_start": "1993-01-29",
             "license": "YF terms", "notes": "adj", "fallback": "stooq:spy.us"}]}))
        w = load_module().build_snapshot(tmp_path)["workspace"]
        c = w["catalog"][0]
        assert c["provider"] == "yahoo" and c["frequency"] == "daily"
        assert c["fallback"] == "stooq:spy.us"
        assert w["catalogCount"] == 1
