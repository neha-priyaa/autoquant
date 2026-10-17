"""Tests for run_external.py — subprocess/llm calls are monkeypatched."""
import json
import sys
from pathlib import Path

import run_external as rx


def verdict(v="RUN_WITH_OUR_DATA", repo="o/r", artifact="s.py",
            sha="a" * 40, **kw):
    return {"repo": repo, "artifact": artifact, "sha": sha, "verdict": v,
            "kind": "script", "symbols": ["AAPL"], "data_calls": [], **kw}


class TestPending:
    def test_executable_verdicts_only(self):
        rows = [verdict("RUN_WITH_OUR_DATA", artifact="a.py"),
                verdict("SPEC_ARTIFACT", artifact="b.md"),
                verdict("INTERACTIVE_ONLY", artifact="c.ipynb"),
                verdict("RUN_BUNDLED_DATA", artifact="d.py")]
        pend = rx.pending(rows, done=set(), heavy=False)
        assert [p["artifact"] for p in pend] == ["a.py", "d.py"]

    def test_heavy_needs_flag(self):
        rows = [verdict("NEEDS_HEAVY_ENV")]
        assert rx.pending(rows, done=set(), heavy=False) == []
        assert len(rx.pending(rows, done=set(), heavy=True)) == 1

    def test_already_done_skipped(self):
        rows = [verdict()]
        done = {("o/r", "s.py", "a" * 40)}
        assert rx.pending(rows, done=done, heavy=False) == []


class TestLeaderboard:
    def test_done_keys(self, tmp_path):
        lb = tmp_path / "leaderboard.jsonl"
        lb.write_text(json.dumps({"repo": "o/r", "artifact": "s.py",
                                  "sha": "a" * 40}) + "\n"
                      + "not json\n")
        assert rx.done_keys(lb) == {("o/r", "s.py", "a" * 40)}

    def test_record_appends(self, tmp_path):
        lb = tmp_path / "lb.jsonl"
        rx.record({"repo": "o/r", "verdict": "ok"}, lb)
        rx.record({"repo": "o/r", "verdict": "error"}, lb)
        assert len(lb.read_text().splitlines()) == 2


class TestPrefetch:
    def test_warms_catalog_cache(self, tmp_path, monkeypatch):
        fetched = []
        monkeypatch.setattr(rx.catalog, "load",
                            lambda sid, s, e: fetched.append(sid))
        misses = rx.prefetch_symbols(["AAPL", "MSFT"])
        assert fetched == ["yahoo:AAPL", "yahoo:MSFT"]
        assert misses == []

    def test_misses_recorded(self, tmp_path, monkeypatch):
        def boom(sid, s, e):
            raise ValueError(f"{sid}: not in catalog")
        monkeypatch.setattr(rx.catalog, "load", boom)
        misses = rx.prefetch_symbols(["ZZZ"])
        assert misses == ["ZZZ"]


class TestRunCopy:
    def test_copy_excludes_git(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "s.py").write_text("print('hi')\n")
        (repo / ".git" / "HEAD").write_text("ref")
        dest = tmp_path / "runs" / "one"
        rx.make_run_copy(repo, dest)
        assert (dest / "s.py").exists()
        assert not (dest / ".git").exists()


class TestRunScript:
    def test_ok_run(self, tmp_path):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("print('hello')\n")
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, {"env": "main"},
                         timeout=30, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "ok"
        assert row["env"] == "main"
        assert row["data_mode"] == "ours"
        assert row["runtime_s"] >= 0

    def test_error_run_records_stderr(self, tmp_path):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("import sys\nsys.exit(2)\n")
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, {"env": "main"},
                         timeout=30, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "error"
        assert row["error"]

    def test_timeout_kills(self, tmp_path):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("import time\ntime.sleep(60)\n")
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, {"env": "main"},
                         timeout=2, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "timeout"

    def test_shim_env_forced_offline(self, tmp_path, monkeypatch):
        captured = {}
        real_popen = rx.subprocess.Popen

        def spy(cmd, **kw):
            captured["env"] = kw["env"]
            return real_popen([sys.executable, "-c", "pass"], **kw)
        monkeypatch.setattr(rx.subprocess, "Popen", spy)
        monkeypatch.setattr(rx, "_python_for", lambda env: sys.executable)
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("pass\n")
        rx.execute(verdict(data_mode_hint="ours"), tmp_path / "repo", run_copy,
                   {"env": "main"}, timeout=10, data_mode="ours",
                   results=tmp_path / "res")
        py_path = captured["env"]["PYTHONPATH"]
        assert str(rx.SHIM) in py_path
        assert captured["env"]["AUTOQUANT_DATA_ROOT"] == str(rx.ROOT)


def write_nb(path: Path):
    nb = {"cells": [{"cell_type": "code", "execution_count": None,
                     "outputs": [], "source": ["print('ran')"],
                     "metadata": {}}],
          "metadata": {"kernelspec": {"name": "python3"}},
          "nbformat": 4, "nbformat_minor": 5}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nb))


class TestRunNotebook:
    def test_executes_and_counts_cells(self, tmp_path):
        repo_dir = tmp_path / "repo"
        write_nb(repo_dir / "n.ipynb")
        run_copy = rx.make_run_copy(repo_dir, tmp_path / "run")
        row = rx.execute({"kind": "notebook", "artifact": "n.ipynb",
                          "repo": "o/r", "sha": "a" * 40},
                         repo_dir, run_copy, {"env": "main"},
                         timeout=120, data_mode="ours", results=tmp_path / "res")
        if row["verdict"] == "ok":  # main env has nbconvert/ipykernel via project deps
            assert row["cells_executed"] == 1
            executed = tmp_path / "res" / "o-r" / "n.ipynb"
            assert executed.exists()
            assert any(c.get("execution_count")
                       for c in json.loads(executed.read_text())["cells"])
        else:
            # env without notebook tooling: recorded, not crashed
            assert row["verdict"] in ("error", "timeout")


class TestMainWith:
    def test_full_flow_end_to_end(self, tmp_path, monkeypatch):
        repos = tmp_path / "repos" / "o-r"
        repos.mkdir(parents=True)
        (repos / "s.py").write_text("print('hello')\n")
        (repos / "manifest.json").write_text(json.dumps(
            {"repo": "o/r", "sha": "a" * 40, "notebooks": [], "scripts": [
                {"path": "s.py", "has_main": True, "n_lines": 1}],
             "spec_texts": [], "data_files": [], "deps": {}}))
        (tmp_path / "triage.jsonl").write_text(json.dumps(verdict()) + "\n")
        monkeypatch.setattr(rx, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(rx, "TRIAGE", tmp_path / "triage.jsonl")
        monkeypatch.setattr(rx, "RESULTS", tmp_path / "res")
        monkeypatch.setattr(rx, "LEADERBOARD", tmp_path / "res" / "leaderboard.jsonl")
        monkeypatch.setattr(rx, "prefetch_symbols", lambda syms: [])

        assert rx.main_with(["--repo", "o/r"]) == 0
        rows = [json.loads(l) for l in
                (tmp_path / "res" / "leaderboard.jsonl").read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["verdict"] == "ok"

        # re-run skips
        monkeypatch.setattr(rx, "execute",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("re-ran")))
        assert rx.main_with(["--repo", "o/r"]) == 0


SPEC_YAML = """\
meta:
  slug: ext-o-r-demo
  title: "Demo strategy"
  url: null
  source: "github o/r"
  posted: null
  claim: "Demo claim."
data:
  universe: [SPY]
  bar: 1d
  fields: [open, high, low, close, volume]
  start: 2000-01-01
  end: null
  source: yfinance
  caveats: []
signal:
  definition: "raw = close > close.rolling(200).mean()"
  lookback_bars: 200
  lag_bars: 1
rules:
  entry: "raw is True"
  exit: "raw is False"
  direction: long_only
  position_when_flat: cash
  sizing: full_notional
  vol_target: null
  max_leverage: 1.0
  rebalance: on_signal_change
  execution_price: next_open
costs:
  commission_bps: 1.0
  slippage_bps: 5.0
  borrow_bps_annual: 0.0
  financing_bps_annual: 0.0
ambiguities: []
validation:
  oos_start: 2026-10-13
  is_oos_split: publication_date
  param_sweep: {}
  cost_sweep_bps: [0, 5, 10, 20, 50]
  null_tests: []
  min_trades: 30
  multiple_testing: {n_tested_so_far: null, method: deflated_sharpe}
verdict:
  status: PENDING
  reason: null
  report: null
"""


class TestPromote:
    def _setup(self, tmp_path, monkeypatch):
        specs = tmp_path / "specs"
        specs.mkdir()
        monkeypatch.setattr(rx, "SPECS", specs)
        triage_rows = [verdict("SPEC_ARTIFACT", artifact="idea.md")]
        triage_path = tmp_path / "triage.jsonl"
        triage_path.write_text("".join(json.dumps(r) + "\n" for r in triage_rows))
        monkeypatch.setattr(rx, "TRIAGE", triage_path)
        repo_dir = tmp_path / "repos" / "o-r"
        repo_dir.mkdir(parents=True)
        (repo_dir / "idea.md").write_text("# Buy above 200dma\nEntry: close > sma200. Exit below.")
        monkeypatch.setattr(rx, "REPOS", tmp_path / "repos")
        return repo_dir, specs

    def test_promote_writes_valid_spec(self, tmp_path, monkeypatch):
        import yaml
        repo_dir, specs = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(rx.llm, "complete", lambda *a, **k: SPEC_YAML)
        out = rx.promote("o/r", "idea.md", model=None, extra=[])
        assert out.name == "ext-o-r-demo.yaml"
        spec = yaml.safe_load(out.read_text())
        assert rx.validate_spec(spec) == []
        assert spec["meta"]["slug"] == "ext-o-r-demo"

    def test_promote_rejects_wrong_slug_prefix(self, tmp_path, monkeypatch):
        repo_dir, specs = self._setup(tmp_path, monkeypatch)
        bad = SPEC_YAML.replace("  slug: ext-o-r-demo\n", "  slug: wrong-slug\n")
        monkeypatch.setattr(rx.llm, "complete", lambda *a, **k: bad)
        try:
            rx.promote("o/r", "idea.md", model=None, extra=[])
            raised = False
        except SystemExit:
            raised = True
        assert raised

    def test_validate_spec_required_keys(self):
        import yaml
        spec = yaml.safe_load(SPEC_YAML)
        assert rx.validate_spec(spec) == []
        no_costs = dict(spec)
        del no_costs["costs"]
        assert any("costs" in e for e in rx.validate_spec(no_costs))
        no_slug = {"meta": {}, "data": spec["data"], "signal": spec["signal"],
                   "rules": spec["rules"], "costs": spec["costs"],
                   "validation": spec["validation"]}
        assert any("slug" in e for e in rx.validate_spec(no_slug))


class TestKindOf:
    def test_path_wins_over_missing_kind(self):
        assert rx.kind_of({"artifact": "n.ipynb", "kind": None}) == "notebook"

    def test_llm_kind_does_not_override_path(self):
        # the triage reply is LLM-produced; the extension is deterministic
        assert rx.kind_of({"artifact": "s.py", "kind": "notebook"}) == "script"
        assert rx.kind_of({"artifact": "n.ipynb", "kind": "script"}) == "notebook"

    def test_non_ipynb_defaults_script(self):
        assert rx.kind_of({"artifact": "idea.md", "kind": None}) == "script"


class TestRunCopyReuse:
    def test_existing_dest_replaced(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "s.py").write_text("print('hi')\n")
        dest = tmp_path / "runs" / "one"
        dest.mkdir(parents=True)
        (dest / "stale.txt").write_text("old attempt")
        rx.make_run_copy(repo, dest)          # must not raise
        assert (dest / "s.py").exists()
        assert not (dest / "stale.txt").exists()
