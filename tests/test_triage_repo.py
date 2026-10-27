"""Tests for triage_repo.py — llm is monkeypatched, no network."""
import json
from pathlib import Path

import triage_repo as tr


MANIFEST = {
    "repo": "o/r", "sha": "a" * 40,
    "notebooks": [{"path": "n.ipynb", "kernel": "python3", "has_outputs": False, "n_cells": 3}],
    "scripts": [{"path": "s.py", "has_main": True, "n_lines": 10}],
    "spec_texts": [{"path": "idea.md"}],
    "data_files": [{"path": "d.csv", "bytes": 10}],
    "deps": {"requirements_txt": "requirements.txt"},
}


class TestArtifacts:
    def test_every_executable_kind_listed(self):
        arts = tr.artifacts(MANIFEST)
        assert [(a["kind"], a["path"]) for a in arts] == [
            ("notebook", "n.ipynb"), ("script", "s.py"), ("spec_text", "idea.md")]

    def test_empty_manifest(self):
        assert tr.artifacts({}) == []


class TestExcerpt:
    def test_notebook_cells_joined(self, tmp_path):
        (tmp_path / "n.ipynb").write_text(json.dumps(
            {"cells": [{"cell_type": "code", "outputs": [], "source": ["import yfinance as yf\n",
                                                                   "yf.download('AAPL')"]}]}))
        text = tr.excerpt(tmp_path, "n.ipynb")
        assert "yf.download('AAPL')" in text
        assert '"cell_type"' not in text  # sources, not the raw json envelope

    def test_plain_text_truncated(self, tmp_path):
        (tmp_path / "s.py").write_text("x = 1\n" * 50_000)
        text = tr.excerpt(tmp_path, "s.py")
        assert len(text) <= tr.MAX_CHARS + 40  # truncation marker allowed
        assert text.endswith("[...truncated for length...]")


class TestBuildPrompt:
    def test_rubric_then_parseable_payload(self, tmp_path):
        (tmp_path / "s.py").write_text("import pandas\n")
        prompt = tr.build_prompt("RUBRIC", MANIFEST, tmp_path,
                                 {"path": "s.py", "kind": "script"})
        assert prompt.startswith("RUBRIC")
        payload = json.loads(prompt[prompt.rindex("\n{\n"):])
        assert payload["repo"] == "o/r"
        assert payload["artifact"] == "s.py"
        assert payload["kind"] == "script"
        assert "import pandas" in payload["text"]

    def test_deps_verbatim_in_payload(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pandas==1.3.0\n")
        prompt = tr.build_prompt("RUBRIC", MANIFEST, tmp_path,
                                 {"path": "s.py", "kind": "script"})
        payload = json.loads(prompt[prompt.rindex("\n{\n"):])
        assert "pandas==1.3.0" in payload["deps_text"]


VERDICT = json.dumps({
    "verdict": "RUN_WITH_OUR_DATA", "symbols": ["AAPL"],
    "data_calls": ["yf.download"], "heavy_deps": [],
    "runtime_class": "seconds", "old_pandas": False,
    "confidence": 0.9, "reason": "simple yf.download usage",
})


class TestScoreOne:
    def _setup_repo(self, tmp_path):
        (tmp_path / "s.py").write_text("import pandas\n")
        manifest = dict(MANIFEST, sha="a" * 40)
        return manifest

    def test_ok(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: VERDICT)
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row["verdict"] == "RUN_WITH_OUR_DATA"
        assert row["repo"] == "o/r" and row["artifact"] == "s.py"
        assert row["sha"] == "a" * 40
        assert "error" not in row

    def test_llm_error_recorded(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)

        def boom(*a, **k):
            raise tr.llm.LLMError("CLI timed out after 300s")
        monkeypatch.setattr(tr.llm, "complete", boom)
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row == {"repo": "o/r", "artifact": "s.py",
                       "error": "CLI timed out after 300s"}

    def test_unparseable_reply(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: "no json here")
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row["error"].startswith("unparseable reply")

    def test_non_dict_reply(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)
        monkeypatch.setattr(tr.llm, "complete",
                            lambda *a, **k: "```json\n[1, 2]\n```")
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row == {"repo": "o/r", "artifact": "s.py",
                       "error": "unparseable reply: not a JSON object"}


class TestMainWith:
    def test_scores_pending_and_resumes(self, tmp_path, monkeypatch):
        repos = tmp_path / "repos" / "o-r"
        repos.mkdir(parents=True)
        (repos / "s.py").write_text("import pandas\n")
        (repos / "manifest.json").write_text(json.dumps(MANIFEST))
        monkeypatch.setattr(tr, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(tr, "TRIAGE", tmp_path / "repo_triage.jsonl")
        monkeypatch.setattr(tr, "PROMPT", Path(tr.__file__).parent / "repo_triage_prompt.md")
        monkeypatch.setattr(tr.llm, "preflight", lambda: None)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: VERDICT)

        assert tr.main_with(["--repo", "o/r"]) == 0
        rows = [json.loads(l) for l in
                (tmp_path / "repo_triage.jsonl").read_text().splitlines()]
        assert {r["artifact"] for r in rows} == {"n.ipynb", "s.py", "idea.md"}

        # re-run is a no-op
        calls = []
        monkeypatch.setattr(tr.llm, "complete",
                            lambda *a, **k: calls.append(1) or VERDICT)
        assert tr.main_with(["--repo", "o/r"]) == 0
        assert calls == []
