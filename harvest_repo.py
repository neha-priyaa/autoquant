#!/usr/bin/env python3
"""Stage [E1] REPO HARVEST — shallow-clone strategy repos + inventory manifest.

    python3 harvest_repo.py LastAncientOne/Stock_Analysis_For_Quant
    python3 harvest_repo.py --repos-file pilot_repos.txt

Clones https://github.com/<owner>/<repo> --depth 1 into
data/repos/<owner>-<repo>/ and writes data/repos/<owner>-<repo>/manifest.json:

    {
      "repo": "owner/name",
      "sha": "<40-hex pinned commit>",
      "cloned_at": "<iso8601>",
      "notebooks":  [{"path", "kernel", "has_outputs", "n_cells", "unparsable"?}],
      "scripts":    [{"path", "has_main", "n_lines"}],
      "spec_texts": [{"path"}],            # md/yaml mentioning strategy terms
      "data_files": [{"path", "bytes"}],   # csv/parquet/h5/pkl/feather
      "deps": {"requirements_txt"|"environment_yml"|"setup_py"|"pyproject_toml":
               "relpath"|null}
    }

Resumable: a repo whose manifest records the remote HEAD sha is skipped; a
changed sha triggers a fresh shallow clone. data/repos/ is covered by the
data/ gitignore rule.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "data" / "repos"

DATA_EXTS = {".csv", ".parquet", ".h5", ".hdf5", ".pkl", ".pickle", ".feather"}
SPEC_TEXT_EXTS = {".md", ".yaml", ".yml"}
SPEC_TEXT_KEYWORDS = ("entry", "signal", "position", "backtest", "allocation",
                      "stop", "rebalance", "strategy")
DEP_KEYS = {"requirements.txt": "requirements_txt", "environment.yml": "environment_yml",
            "setup.py": "setup_py", "pyproject.toml": "pyproject_toml"}
SKIP_DIRS = {".git", ".ipynb_checkpoints", "__pycache__", ".venv", "venv",
             "node_modules"}


def repo_slug(owner_repo: str) -> str:
    """'owner/name' -> 'owner-name' (directory name under data/repos/)."""
    return owner_repo.strip("/").replace("/", "-")


def remote_sha(owner_repo: str) -> str | None:
    """Remote HEAD sha without cloning; None if the repo is unreachable."""
    proc = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{owner_repo}", "HEAD"],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split()[0]


def clone(owner_repo: str, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        ["git", "clone", "--depth", "1",
         f"https://github.com/{owner_repo}.git", str(dest)],
        capture_output=True, text=True, timeout=1800)
    if proc.returncode != 0:
        raise RuntimeError(f"clone failed: {proc.stderr.strip()[:200]}")


def _is_spec_text(path: Path) -> bool:
    try:
        head = path.read_text(errors="ignore")[:4000].lower()
    except OSError:
        return False
    return any(k in head for k in SPEC_TEXT_KEYWORDS)


def _scan_notebook(rel: str, path: Path) -> dict:
    row: dict = {"path": rel, "kernel": None, "has_outputs": False, "n_cells": 0}
    try:
        nb = json.loads(path.read_text(errors="ignore"))
    except (json.JSONDecodeError, OSError):
        row["unparsable"] = True
        return row
    cells = nb.get("cells", [])
    row["n_cells"] = len(cells)
    row["kernel"] = (nb.get("metadata", {}).get("kernelspec", {}) or {}).get("name")
    row["has_outputs"] = any(c.get("outputs") for c in cells)
    return row


def scan(repo_dir: Path) -> dict:
    """Inventory the cloned tree into manifest sections (schema: docstring)."""
    notebooks, scripts, spec_texts, data_files = [], [], [], []
    deps = {key: None for key in DEP_KEYS.values()}
    for path in sorted(repo_dir.rglob("*")):
        rel = str(path.relative_to(repo_dir))
        if path.is_dir():
            continue
        if set(path.parts) & SKIP_DIRS:
            continue
        name = path.name
        if name in DEP_KEYS and path.parent == repo_dir:
            deps[DEP_KEYS[name]] = name
        if path.suffix == ".ipynb":
            notebooks.append(_scan_notebook(rel, path))
        elif path.suffix == ".py":
            try:
                text = path.read_text(errors="ignore")
            except OSError:
                continue
            scripts.append({"path": rel, "has_main": "if __name__" in text,
                            "n_lines": len(text.splitlines())})
        elif path.suffix in SPEC_TEXT_EXTS and _is_spec_text(path):
            spec_texts.append({"path": rel})
        elif path.suffix in DATA_EXTS:
            data_files.append({"path": rel, "bytes": path.stat().st_size})
    return {"notebooks": notebooks, "scripts": scripts, "spec_texts": spec_texts,
            "data_files": data_files, "deps": deps}


def harvest_one(owner_repo: str, out_root: Path) -> tuple[str, str]:
    """Clone + manifest one repo. Returns (status, detail):
    status is 'ok' | 'skip' | 'error'."""
    dest = out_root / repo_slug(owner_repo)
    manifest_path = dest / "manifest.json"
    try:
        sha = remote_sha(owner_repo)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return "error", f"{owner_repo}: ls-remote failed: {exc}"
    if sha is None:
        return "error", f"{owner_repo}: unreachable (ls-remote failed)"
    if manifest_path.exists():
        try:
            old = json.loads(manifest_path.read_text())
            if old.get("sha") == sha:
                return "skip", f"{owner_repo} already at {sha[:12]}"
        except (json.JSONDecodeError, OSError):
            pass  # torn manifest — fall through to a fresh clone
    try:
        clone(owner_repo, dest)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return "error", f"{owner_repo}: {exc}"
    manifest = scan(dest)
    manifest.update({
        "repo": owner_repo,
        "sha": sha,
        "cloned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    counts = {k: len(manifest[k]) for k in
              ("notebooks", "scripts", "spec_texts", "data_files")}
    return "ok", f"{owner_repo} @ {sha[:12]}  {counts}"
