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
