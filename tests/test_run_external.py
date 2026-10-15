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
