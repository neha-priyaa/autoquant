"""Tests for run_external.py — subprocess/llm calls are monkeypatched."""
import json
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
