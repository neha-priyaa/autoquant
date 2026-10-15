#!/usr/bin/env python3
"""Stage [E5] EXTERNAL RUN — execute triaged repo artifacts, record verdicts.

Executes artifacts whose triage verdict is RUN_WITH_OUR_DATA or
RUN_BUNDLED_DATA (NEEDS_HEAVY_ENV behind --heavy). Each artifact runs in a
fresh run-copy of the repo, in its per-repo env (repo_env), with the
external_shim on PYTHONPATH forcing offline execution against our price
cache (RUN_WITH_OUR_DATA). Notebooks execute via nbconvert in the repo venv;
scripts via an isolated subprocess with a hard timeout (process-group kill
on expiry, same pattern as backtest_batch.py).

Results: results/external/<repo>/<artifact-stem>.ipynb (executed notebooks,
browsable evidence) and results/external/leaderboard.jsonl (append-only, one
row per attempt). Re-runs skip (repo, artifact, sha) triples already on the
leaderboard.

Promotion: --promote <repo>/<artifact> ports a SPEC_ARTIFACT (directly) or
an executed artifact (LLM-reviewed) into specs/ext-<repo>-<slug>.yaml so it
enters the existing backtest lane.

    python3 run_external.py --repo owner/name
    python3 run_external.py --repo owner/name --heavy --timeout 900
    python3 run_external.py --promote owner/name/idea.md
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import catalog
import llm
import repo_env
from triage import load, save

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "data" / "repos"
TRIAGE = ROOT / "data" / "repo_triage.jsonl"
RESULTS = ROOT / "results" / "external"
LEADERBOARD = RESULTS / "leaderboard.jsonl"
SHIM = ROOT / "external_shim"
TEMPLATE = ROOT / "_TEMPLATE.yaml"

EXECUTABLE = {"RUN_WITH_OUR_DATA", "RUN_BUNDLED_DATA"}
DEFAULT_TIMEOUT = 600


def done_keys(leaderboard: Path) -> set[tuple[str, str, str]]:
    """(repo, artifact, sha) triples with a leaderboard row. Tolerates torn
    lines (same contract as backtest_batch.already_run)."""
    if not leaderboard.exists():
        return set()
    done = set()
    for line in leaderboard.read_text().splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("repo"):
            done.add((row["repo"], row.get("artifact"), row.get("sha")))
    return done


def pending(verdicts: list[dict], done: set, heavy: bool) -> list[dict]:
    allowed = EXECUTABLE | ({"NEEDS_HEAVY_ENV"} if heavy else set())
    return [v for v in verdicts
            if v.get("verdict") in allowed
            and (v["repo"], v.get("artifact"), v.get("sha")) not in done]


def record(row: dict, leaderboard: Path) -> None:
    leaderboard.parent.mkdir(parents=True, exist_ok=True)
    with leaderboard.open("a") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
