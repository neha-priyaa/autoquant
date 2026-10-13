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
