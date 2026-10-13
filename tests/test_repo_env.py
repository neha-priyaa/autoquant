"""Tests for repo_env.py — uv/git invocations are monkeypatched."""
import json
from pathlib import Path

import repo_env as re_


def manifest_with(**deps) -> dict:
    base = {"repo": "o/r", "sha": "a" * 40,
            "deps": {"requirements_txt": None, "environment_yml": None,
                     "setup_py": None, "pyproject_toml": None}}
    base["deps"].update(deps)
    return base


class TestEnsureEnv:
    def test_no_deps_uses_main_env(self, tmp_path):
        info = re_.ensure_env(tmp_path, manifest_with())
        assert info == {"env": "main"}

    def test_builds_venv_from_requirements(self, tmp_path, monkeypatch):
        req = tmp_path / "requirements.txt"
        req.write_text("pandas==1.3.0\n")
        calls = []
        monkeypatch.setattr(re_, "_run", lambda cmd: calls.append(cmd) or (0, ""))
        info = re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        assert info["env"] == "venv"
        assert info["python"] == str(tmp_path / ".venv" / "bin" / "python")
        joined = " ".join(calls[0])
        assert ".venv" in joined
        assert any("requirements.txt" in " ".join(c) for c in calls)
        # nbconvert + ipykernel installed for notebook execution
        assert any("nbconvert" in " ".join(c) for c in calls)

    def test_reuses_matching_key(self, tmp_path, monkeypatch):
        req = tmp_path / "requirements.txt"
        req.write_text("pandas==1.3.0\n")
        monkeypatch.setattr(re_, "_run", lambda cmd: (0, ""))
        first = re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        calls = []
        monkeypatch.setattr(re_, "_run", lambda cmd: calls.append(cmd) or (0, ""))
        second = re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        assert second == first
        assert calls == []  # nothing rebuilt

    def test_rebuilds_when_deps_change(self, tmp_path, monkeypatch):
        req = tmp_path / "requirements.txt"
        req.write_text("pandas==1.3.0\n")
        monkeypatch.setattr(re_, "_run", lambda cmd: (0, ""))
        re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        req.write_text("pandas==2.0.0\n")
        calls = []
        monkeypatch.setattr(re_, "_run", lambda cmd: calls.append(cmd) or (0, ""))
        re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        assert calls  # rebuilt

    def test_talib_is_unsupported(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("ta-lib\n")
        info = re_.ensure_env(tmp_path, manifest_with(requirements_txt="requirements.txt"))
        assert info["env"] == "unsupported"
        assert "ta-lib" in info["reason"]

    def test_conda_only_env_yml_unsupported(self, tmp_path):
        (tmp_path / "environment.yml").write_text(
            "name: q\ndependencies:\n  - python=3.7\n  - pandas=0.25\n")
        info = re_.ensure_env(tmp_path, manifest_with(environment_yml="environment.yml"))
        assert info["env"] == "unsupported"

    def test_setup_py_only_unsupported(self, tmp_path):
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup()\n")
        info = re_.ensure_env(tmp_path, manifest_with(setup_py="setup.py"))
        assert info["env"] == "unsupported"


class TestLegacy:
    def test_builds_legacy_venv_once(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr(re_, "_run", lambda cmd: calls.append(cmd) or (0, ""))
        info = re_.legacy_env(tmp_path)
        assert info["env"] == "venv-legacy"
        assert ".venv-legacy" in info["python"]
        assert any("pandas<1.4" in " ".join(c) for c in calls)
        assert len([c for c in calls if "uv" in c[0]]) >= 2
        calls.clear()
        re_.legacy_env(tmp_path)  # second call reuses
        assert calls == []

    def test_has_pins(self, tmp_path):
        assert re_.has_pins("pandas==1.3.0\n") is True
        assert re_.has_pins("pandas\nnumpy\n") is False
        assert re_.has_pins("") is False

    def test_legacy_worth_retry(self):
        assert re_.legacy_worth_retry(
            "AttributeError: module 'pandas' has no attribute 'xyz'",
            env_used="main", has_pins=False) is True
        assert re_.legacy_worth_retry(
            "AttributeError: ...", env_used="venv-legacy", has_pins=False) is False
        assert re_.legacy_worth_retry(
            "AttributeError: ...", env_used="main", has_pins=True) is False
        assert re_.legacy_worth_retry(
            "error: file not found", env_used="main", has_pins=False) is False
