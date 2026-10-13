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

    def test_broken_symlink_does_not_crash(self, tmp_path):
        import os
        r = make_repo(tmp_path)
        os.symlink("/nonexistent", r / "broken.csv")
        m = hr.scan(r)
        by_path = {d["path"]: d for d in m["data_files"]}
        assert by_path["broken.csv"]["bytes"] == 0


class TestHarvestOne:
    def test_clones_and_writes_manifest(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "remote_sha", lambda r: "a" * 40)
        calls = []
        monkeypatch.setattr(hr, "clone", lambda repo, dest: calls.append((repo, dest)))
        status, detail = hr.harvest_one("o/r", tmp_path)
        assert status == "ok"
        assert calls == [("o/r", tmp_path / "o-r")]
        m = json.loads((tmp_path / "o-r" / "manifest.json").read_text())
        assert m["repo"] == "o/r" and m["sha"] == "a" * 40
        assert "cloned_at" in m

    def test_skip_when_same_sha(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "remote_sha", lambda r: "a" * 40)
        dest = tmp_path / "o-r"
        dest.mkdir()
        (dest / "manifest.json").write_text(json.dumps({"sha": "a" * 40}))
        status, _ = hr.harvest_one("o/r", tmp_path)
        assert status == "skip"

    def test_reclone_when_sha_changed(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "remote_sha", lambda r: "b" * 40)
        monkeypatch.setattr(hr, "clone", lambda repo, dest: None)
        dest = tmp_path / "o-r"
        dest.mkdir()
        (dest / "manifest.json").write_text(json.dumps({"sha": "a" * 40}))
        status, _ = hr.harvest_one("o/r", tmp_path)
        assert status == "ok"

    def test_unreachable_repo_is_error_not_crash(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "remote_sha", lambda r: None)
        status, detail = hr.harvest_one("o/gone", tmp_path)
        assert status == "error"

    def test_malformed_slug_is_error_before_network(self, tmp_path, monkeypatch):
        def boom(r):
            raise AssertionError("remote_sha must not be called")
        monkeypatch.setattr(hr, "remote_sha", boom)
        status, detail = hr.harvest_one("..", tmp_path)
        assert status == "error"
        assert "expected OWNER/REPO" in detail


class TestMainWith:
    def test_reports_and_exits_zero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(hr, "remote_sha", lambda r: "a" * 40)
        monkeypatch.setattr(hr, "clone", lambda repo, dest: None)
        rc = hr.main_with(["o/r"])
        assert rc == 0
        assert (tmp_path / "repos" / "o-r" / "manifest.json").exists()

    def test_repos_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(hr, "remote_sha", lambda r: "a" * 40)
        monkeypatch.setattr(hr, "clone", lambda repo, dest: None)
        repos_file = tmp_path / "repos.txt"
        repos_file.write_text("o/one\no/two\n")
        rc = hr.main_with(["--repos-file", str(repos_file)])
        assert rc == 0
        assert (tmp_path / "repos" / "o-one" / "manifest.json").exists()
        assert (tmp_path / "repos" / "o-two" / "manifest.json").exists()

    def test_all_errors_exit_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr(hr, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(hr, "remote_sha", lambda r: None)
        assert hr.main_with(["o/gone"]) != 0
