"""Per-repo execution environments — uv venvs, never the project env.

Third-party repos have conflicting dependencies (2018-era pandas vs pandas
2/3). repo_env builds one uv venv per repo at data/repos/<repo>/.venv and is
reused across runs; the reuse key is sha256(repo sha + deps-file content),
stored in data/repos/<repo>/.env.json. No repo dependency ever touches the
project uv.lock — every install targets the per-repo venv explicitly.

Supported dep declarations: requirements.txt (fully), environment.yml (only
its `pip:` sublist — conda-only deps are unsupported), setup.py /
pyproject.toml (unsupported — we do not install foreign packages as code).
ta-lib anywhere in the deps => unsupported: it needs a system C library we
do not build; artifacts are SKIPped with that reason at run time.

Repos with no declared deps run in the main project env (env: "main").

Not safe for concurrent calls on the same repo_dir — callers must dispatch
one thread per repo.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "data" / "repos"

# Notebook execution support, installed into every repo venv (never project).
EXEC_DEPS = ["nbconvert", "ipykernel"]

# Fallback env: older interpreter + pandas 1.x-era pin set (issue #25).
LEGACY_PYTHON = "3.9"
LEGACY_PINS = ["pandas<1.4", "numpy<1.24", "matplotlib"] + EXEC_DEPS

HEAVY_MARKERS = ("ta-lib", "talib")


def _run(cmd: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"[:300]
    return proc.returncode, (proc.stderr or proc.stdout)[-300:]


def _state_path(repo_dir: Path) -> Path:
    return repo_dir / ".env.json"


def _write_state(path: Path, info: dict) -> None:
    """Atomic write: tmp file + replace, so readers never see a torn state."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(info) + "\n")
    tmp.replace(path)


def _pip_sublist(yml_text: str) -> list[str] | None:
    """Entries under environment.yml's `pip:` sublist, or None if absent."""
    try:
        doc = yaml.safe_load(yml_text)
    except yaml.YAMLError:
        return None
    if not isinstance(doc, dict):
        return None
    deps = doc.get("dependencies")
    if not isinstance(deps, list):
        return None
    for entry in deps:
        if isinstance(entry, dict) and "pip" in entry:
            pip = entry["pip"]
            if not isinstance(pip, list):
                return None
            return [str(item) for item in pip
                    if str(item).strip() and not str(item).strip().startswith("#")]
    return None


def _deps_paths(repo_dir: Path, manifest: dict) -> list[Path]:
    out = []
    for key in ("requirements_txt", "environment_yml", "setup_py", "pyproject_toml"):
        rel = manifest.get("deps", {}).get(key)
        if rel and (repo_dir / rel).exists():
            out.append(repo_dir / rel)
    return out


def _env_key(manifest: dict, deps_paths: list[Path]) -> str:
    h = hashlib.sha256()
    h.update((manifest.get("sha") or "").encode())
    for p in deps_paths:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def _pip_install(python: Path, reqs: list[str]) -> tuple[int, str]:
    """Install into the venv via uv pip, targeting its interpreter."""
    if reqs:
        rc, err = _run(["uv", "pip", "install", "--python", str(python), *reqs])
        if rc != 0:
            return rc, err
    return 0, ""


def build_env(repo_dir: Path, manifest: dict) -> dict:
    venv = repo_dir / ".venv"
    python = venv / "bin" / "python"
    rc, err = _run(["uv", "venv", str(venv)])
    if rc != 0:
        return {"env": "unsupported", "reason": f"uv venv failed: {err}"}
    reqs_rel = manifest["deps"].get("requirements_txt")
    if reqs_rel:
        reqs = ["-r", str(repo_dir / reqs_rel)]
    else:
        yml = (repo_dir / manifest["deps"]["environment_yml"]).read_text(errors="ignore")
        pip_entries = _pip_sublist(yml)
        if not pip_entries:
            return {"env": "unsupported", "reason": "no usable dependency list"}
        reqs = pip_entries
    rc, err = _pip_install(python, [*reqs, *EXEC_DEPS])
    if rc != 0:
        return {"env": "unsupported", "reason": f"pip install failed: {err}"}
    return {"env": "venv", "python": str(python)}


def ensure_env(repo_dir: Path, manifest: dict) -> dict:
    """Build or reuse the repo's env. Returns one of:
    {"env": "main"} | {"env": "venv", "python": <path>, "key": <hash>}
    | {"env": "unsupported", "reason": <why>}."""
    deps_paths = _deps_paths(repo_dir, manifest)
    if not deps_paths:
        return {"env": "main"}

    deps_text = "\n".join(p.read_text(errors="ignore") for p in deps_paths)
    if any(marker in deps_text.lower() for marker in HEAVY_MARKERS):
        return {"env": "unsupported",
                "reason": "ta-lib requires a system C library we do not build"}
    if manifest["deps"].get("environment_yml") and not manifest["deps"].get("requirements_txt"):
        yml = (repo_dir / manifest["deps"]["environment_yml"]).read_text(errors="ignore")
        if "pip:" not in yml:
            return {"env": "unsupported",
                    "reason": "conda-only environment.yml (no pip: sublist)"}
    if manifest["deps"].get("setup_py") or manifest["deps"].get("pyproject_toml"):
        return {"env": "unsupported",
                "reason": "setup.py/pyproject-only repos are not installed"}

    key = _env_key(manifest, deps_paths)
    state_path = _state_path(repo_dir)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            if state.get("key") == key and state.get("env") == "venv":
                return state
        except (json.JSONDecodeError, OSError):
            pass

    info = build_env(repo_dir, manifest)
    if info["env"] == "venv":
        info["key"] = key
        _write_state(state_path, info)
    return info


def legacy_env(repo_dir: Path) -> dict:
    """Fallback venv (.venv-legacy): older Python + pandas 1.x-era pins.
    Built on demand and reused (no hash key — a fixed pin set)."""
    state_path = _state_path(repo_dir)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            if state.get("env") == "venv-legacy":
                return state
        except (json.JSONDecodeError, OSError):
            pass
    venv = repo_dir / ".venv-legacy"
    python = venv / "bin" / "python"
    rc, err = _run(["uv", "venv", "--python", LEGACY_PYTHON, str(venv)])
    if rc != 0:
        return {"env": "unsupported", "reason": f"legacy uv venv failed: {err}"}
    rc, err = _pip_install(python, LEGACY_PINS)
    if rc != 0:
        return {"env": "unsupported", "reason": f"legacy pip install failed: {err}"}
    info = {"env": "venv-legacy", "python": str(python)}
    _write_state(state_path, info)
    return info


def has_pins(deps_text: str) -> bool:
    """True when any dependency declares a version constraint."""
    return any(op in deps_text for op in ("==", ">=", "<=", "~=", "!=", ">", "<"))


LEGACY_MARKERS = ("has no attribute", "unexpected keyword", "removed in",
                  "not a function", "cannot import name")


def legacy_worth_retry(error: str, env_used: str, pins: bool) -> bool:
    """Retry in the legacy env only when: the failure looks like a
    pandas/numpy API mismatch, the repo declared no pins, and we have not
    already retried there."""
    if env_used != "main" or pins:
        return False
    return any(m in error for m in LEGACY_MARKERS)
