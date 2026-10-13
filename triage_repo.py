#!/usr/bin/env python3
"""Stage [E2] REPO TRIAGE — LLM runnability scoring per repo artifact.

Reads data/repos/<repo>/manifest.json, scores every notebook/script/spec_text
via repo_triage_prompt.md, and appends verdicts to data/repo_triage.jsonl —
one row per artifact, keyed by (repo, artifact). Re-runs skip scored
artifacts (--rescore overrides).

The lane's contract: triage scores RUNNABILITY, not whether the strategy is
sensible. Verdict enum and rubric live in repo_triage_prompt.md.

    python3 triage_repo.py                    # every manifest under data/repos/
    python3 triage_repo.py --repo owner/name  # one repo
    python3 triage_repo.py --limit 5          # calibrate
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from pathlib import Path

import llm
from triage import load, parse_json, save  # shared jsonl + reply-parsing helpers

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "data" / "repos"
TRIAGE = ROOT / "data" / "repo_triage.jsonl"
PROMPT = ROOT / "repo_triage_prompt.md"

MAX_CHARS = 40_000
MAX_DEPS_CHARS = 4_000
CLI_TIMEOUT = 300


def artifacts(manifest: dict) -> list[dict]:
    """Executable/triagable artifacts from a manifest, in stable order."""
    out = []
    for kind, key in (("notebook", "notebooks"), ("script", "scripts"),
                      ("spec_text", "spec_texts")):
        for row in manifest.get(key, []):
            out.append({"kind": kind, **row})
    return out


def excerpt(repo_dir: Path, rel_path: str) -> str:
    """Artifact text for the prompt. Notebooks: joined cell sources (not the
    json envelope); everything else: raw text. Truncated at MAX_CHARS."""
    path = repo_dir / rel_path
    try:
        raw = path.read_text(errors="ignore")
    except OSError as exc:
        return f"[unreadable: {exc}]"
    if path.suffix == ".ipynb":
        try:
            nb = json.loads(raw)
        except json.JSONDecodeError:
            return raw[:MAX_CHARS]
        parts = []
        for cell in nb.get("cells", []):
            src = cell.get("source", "")
            parts.append("".join(src) if isinstance(src, list) else src)
        raw = "\n\n".join(parts)
    if len(raw) > MAX_CHARS:
        raw = raw[:MAX_CHARS] + "\n\n[...truncated for length...]"
    return raw


def _deps_text(repo_dir: Path, manifest: dict) -> str:
    parts = []
    for key in ("requirements_txt", "environment_yml", "setup_py", "pyproject_toml"):
        rel = manifest.get("deps", {}).get(key)
        if not rel:
            continue
        try:
            text = (repo_dir / rel).read_text(errors="ignore")
        except OSError:
            text = "[unreadable]"
        parts.append(f"--- {rel} ---\n{text[:MAX_DEPS_CHARS]}")
    return "\n".join(parts)


def build_prompt(rubric: str, manifest: dict, repo_dir: Path,
                 artifact: dict) -> str:
    text = excerpt(repo_dir, artifact["path"])
    payload = {
        "repo": manifest["repo"],
        "sha": manifest.get("sha"),
        "artifact": artifact["path"],
        "kind": artifact["kind"],
        "deps_text": _deps_text(repo_dir, manifest),
        "text": text,
    }
    return (
        f"{rubric}\n\n"
        "---\n\nHere is the artifact to triage. Return ONLY the JSON object "
        "described above -- no prose, no markdown fences.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )
