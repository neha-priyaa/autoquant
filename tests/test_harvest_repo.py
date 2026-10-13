"""Tests for harvest_repo.py — all filesystem-fake, no network, no git."""
import json
from pathlib import Path

import harvest_repo as hr


def make_repo(tmp_path: Path) -> Path:
    """A tiny fake cloned repo with one of every artifact kind."""
    nb = {"cells": [
        {"cell_type": "code", "outputs": [{"data": {}}], "source": ["x=1"]},
        {"cell_type": "markdown", "outputs": [], "source": ["# hi"]},
    ], "metadata": {"kernelspec": {"name": "python3"}}}
    (tmp_path / "nb").mkdir()
    (tmp_path / "nb" / "demo.ipynb").write_text(json.dumps(nb))
    (tmp_path / "run_me.py").write_text("import pandas\n\nif __name__ == '__main__':\n    pass\n")
    (tmp_path / "lib.py").write_text("def helper():\n    return 1\n")
    (tmp_path / "strategy.md").write_text("# Mean reversion\n\nEntry when z < -2, exit at 0.")
    (tmp_path / "notes.txt").write_text("not a spec, not scanned")
    (tmp_path / "prices.csv").write_text("date,close\n2020-01-02,100\n")
    (tmp_path / "requirements.txt").write_text("pandas==1.3.0\n")
    return tmp_path


class TestScan:
    def test_notebooks(self, tmp_path):
        m = hr.scan(make_repo(tmp_path))
        assert m["notebooks"] == [{"path": "nb/demo.ipynb", "kernel": "python3",
                                   "has_outputs": True, "n_cells": 2}]

    def test_scripts_flag_mains(self, tmp_path):
        m = hr.scan(make_repo(tmp_path))
        by_path = {s["path"]: s for s in m["scripts"]}
        assert by_path["run_me.py"]["has_main"] is True
        assert by_path["lib.py"]["has_main"] is False
        assert by_path["run_me.py"]["n_lines"] == 4

    def test_spec_texts_keyword_gate(self, tmp_path):
        m = hr.scan(make_repo(tmp_path))
        assert [s["path"] for s in m["spec_texts"]] == ["strategy.md"]

    def test_data_files(self, tmp_path):
        m = hr.scan(make_repo(tmp_path))
        assert m["data_files"] == [{"path": "prices.csv",
                                    "bytes": len("date,close\n2020-01-02,100\n")}]

    def test_deps_declared(self, tmp_path):
        m = hr.scan(make_repo(tmp_path))
        assert m["deps"]["requirements_txt"] == "requirements.txt"
        assert m["deps"]["environment_yml"] is None

    def test_skips_git_and_cruft(self, tmp_path):
        r = make_repo(tmp_path)
        (r / ".git").mkdir()
        (r / ".git" / "evil.ipynb").write_text("{}")
        (r / "__pycache__").mkdir()
        (r / "__pycache__" / "x.py").write_text("x=1")
        m = hr.scan(r)
        assert all(".git" not in s["path"] for s in m["notebooks"])
        assert all("__pycache__" not in s["path"] for s in m["scripts"])

    def test_unparsable_notebook_recorded(self, tmp_path):
        r = make_repo(tmp_path)
        (r / "broken.ipynb").write_text("{not json")
        m = hr.scan(r)
        assert m["notebooks"][0]["unparsable"] is True
