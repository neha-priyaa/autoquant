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
SPECS = ROOT / "specs"

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


def prefetch_symbols(symbols: list[str]) -> list[str]:
    """Warm the catalog cache for the artifact's symbols so the shim (which
    never touches the network) can serve them. Returns symbols that missed."""
    misses = []
    for sym in sorted({s.upper() for s in symbols}):
        try:
            catalog.load(f"yahoo:{sym}", None, None)
        except Exception:
            misses.append(sym)
    return misses


def make_run_copy(repo_dir: Path, dest: Path) -> Path:
    """Fresh copy of the repo minus .git — the original clone never mutates.
    A stale dest from a previous attempt is replaced (resumable re-runs)."""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(repo_dir, dest,
                    ignore=shutil.ignore_patterns(".git", ".venv",
                                                  ".venv-legacy", ".env.json"))
    return dest


def _python_for(env: dict) -> str:
    if env.get("env") == "main":
        return sys.executable
    return env["python"]


def _kill_group(pid: int) -> None:
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _child_env(data_mode: str, repo_root: Path | None = None) -> dict:
    env = os.environ.copy()
    parts = [env.get("PYTHONPATH", "")]
    if repo_root is not None:
        # repo-local modules (e.g. a sibling `backtester/`) must import
        parts.insert(0, str(repo_root))
    if data_mode == "ours":
        # Shim first on the path: `import yfinance` resolves to the stub.
        parts.insert(0, str(SHIM))
        env["AUTOQUANT_DATA_ROOT"] = str(ROOT)
    env["PYTHONPATH"] = os.pathsep.join(parts).rstrip(os.pathsep)
    return env


def _launch(cmd: list[str], cwd: Path, env: dict, timeout: int):
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=cwd, env=env, start_new_session=True)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_group(proc.pid)
        proc.communicate()
        return None, "", f"timed out after {timeout}s"
    return proc.returncode, stdout, stderr


def kind_of(art: dict) -> str:
    """Notebook vs script — derived from the path (deterministic), not the
    LLM's triage reply, which may omit or contradict `kind`."""
    if str(art.get("artifact", "")).endswith(".ipynb"):
        return "notebook"
    return "script"


def execute(art: dict, repo_dir: Path, run_copy: Path, env: dict,
            timeout: int, data_mode: str, results: Path) -> dict:
    """Execute one artifact in the run-copy; return a leaderboard row."""
    target = run_copy / art["artifact"]
    started = time.monotonic()
    if kind_of(art) == "notebook":
        row = _run_notebook(art, target, run_copy, env, timeout, data_mode,
                            results)
    else:
        rc, _out, err = _launch([_python_for(env), str(target)],
                                cwd=run_copy,
                                env=_child_env(data_mode, repo_root=run_copy),
                                timeout=timeout)
        row = {"cells_executed": None, "outputs": []}
        if rc is None:
            row["verdict"], row["error"] = "timeout", err
        elif rc != 0:
            row["verdict"] = "error"
            row["error"] = (err or "").strip().splitlines()[-1][:200] if err.strip() else f"exit {rc}"
        else:
            row["verdict"], row["error"] = "ok", None
    row["runtime_s"] = round(time.monotonic() - started, 2)
    row["env"] = env.get("env")
    row["data_mode"] = data_mode
    return row


def _run_notebook(art: dict, nb_path: Path, repo_root: Path, env: dict,
                  timeout: int, data_mode: str, results: Path) -> dict:
    """Execute via nbconvert in the artifact's env; save the executed
    notebook (inline outputs = browsable evidence) under results/."""
    cmd = [_python_for(env), "-m", "nbconvert", "--to", "notebook",
           "--execute", "--inplace",
           f"--ExecutePreprocessor.timeout={min(timeout, 120)}",
           "--ExecutePreprocessor.kernel_name=python3",
           str(nb_path)]
    rc, _out, err = _launch(cmd, cwd=nb_path.parent,
                            env=_child_env(data_mode, repo_root=repo_root),
                            timeout=timeout)
    row: dict = {"cells_executed": None, "outputs": []}
    if rc is None:
        row["verdict"], row["error"] = "timeout", err
        return row
    if rc != 0:
        row["verdict"] = "error"
        row["error"] = (err or "").strip().splitlines()[-1][:200] if err.strip() else f"exit {rc}"
        return row
    try:
        nb = json.loads(nb_path.read_text())
        row["cells_executed"] = sum(1 for c in nb.get("cells", [])
                                    if c.get("execution_count"))
    except (json.JSONDecodeError, OSError):
        pass
    stem = Path(art["artifact"]).stem
    out_dir = results / art["repo"].replace("/", "-")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stem}.ipynb"
    shutil.copy2(nb_path, out)
    row["verdict"], row["error"] = "ok", None
    row["outputs"] = [str(out)]
    return row


def _lead_row(art: dict, row: dict, legacy_retry: bool) -> dict:
    return {
        "repo": art["repo"], "sha": art.get("sha"), "artifact": art["artifact"],
        "kind": kind_of(art), "verdict": row["verdict"],
        "cells_executed": row.get("cells_executed"),
        "runtime_s": row.get("runtime_s"), "env": row.get("env"),
        "data_mode": row.get("data_mode"), "outputs": row.get("outputs", []),
        "error": row.get("error"), "legacy_retry": legacy_retry,
        "prefetch_misses": row.get("prefetch_misses", []),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def run_one(art: dict, repo_dir: Path, timeout: int) -> dict:
    """One artifact end-to-end: env, prefetch, run-copy, execute, legacy
    retry. Returns the leaderboard row."""
    manifest = json.loads((repo_dir / "manifest.json").read_text())
    env = repo_env.ensure_env(repo_dir, manifest)
    if env.get("env") == "unsupported":
        return _lead_row(art, {"verdict": "skip", "error": env.get("reason"),
                               "env": "none", "data_mode": None,
                               "cells_executed": None, "outputs": [],
                               "runtime_s": 0.0}, legacy_retry=False)

    data_mode = "bundled" if art.get("verdict") == "RUN_BUNDLED_DATA" else "ours"
    misses = prefetch_symbols(art.get("symbols", [])) if data_mode == "ours" else []

    stem = Path(art["artifact"]).stem
    run_copy = make_run_copy(repo_dir, RESULTS / repo_dir.name / "runs" / stem)
    row = execute(art, repo_dir, run_copy, env, timeout, data_mode, RESULTS)

    legacy_retry = False
    if (row["verdict"] in ("error", "timeout") and env.get("env") == "main"):
        deps_text = "\n".join(
            (repo_dir / rel).read_text(errors="ignore")
            for rel in manifest.get("deps", {}).values() if rel)
        if repo_env.legacy_worth_retry(row.get("error") or "", env.get("env"),
                                       repo_env.has_pins(deps_text)):
            leg = repo_env.legacy_env(repo_dir)
            if leg.get("env") == "venv-legacy":
                retry = execute(art, repo_dir, run_copy, leg, timeout,
                                data_mode, RESULTS)
                if retry["verdict"] == "ok":
                    row, legacy_retry = retry, True
    row["prefetch_misses"] = misses
    return _lead_row(art, row, legacy_retry)


def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="run only OWNER/REPO")
    ap.add_argument("--jobs", type=int, default=2, help="concurrent artifacts")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help="per-artifact subprocess cap in seconds")
    ap.add_argument("--heavy", action="store_true",
                    help="also execute NEEDS_HEAVY_ENV artifacts")
    ap.add_argument("--promote", metavar="REPO/ARTIFACT", default=None,
                    help="port one artifact into specs/ (manual trigger)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--llm-arg", action="append", default=[], metavar="ARG")
    args = ap.parse_args(argv)

    if args.promote:
        return promote_cli(args.promote, args.model, args.llm_arg)

    verdicts = load(TRIAGE)
    if args.repo:
        verdicts = [v for v in verdicts if v.get("repo") == args.repo]
    todo = pending(verdicts, done_keys(LEADERBOARD), args.heavy)
    if not todo:
        print("nothing to run -- triage first (triage_repo.py), or "
              "everything with a verdict already has a leaderboard row")
        return 0

    print(f"running {len(todo)} artifacts "
          f"({args.jobs} at a time, {args.timeout}s cap each)\n")
    ok = failed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_one, art, REPOS / art["repo"].replace("/", "-"),
                               args.timeout): art for art in todo}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            art = futures[fut]
            try:
                row = fut.result()
            except Exception as exc:  # harness bug or torn state — keep the batch alive
                row = {"repo": art["repo"], "sha": art.get("sha"),
                       "artifact": art["artifact"], "kind": art.get("kind"),
                       "verdict": "error", "error": f"harness: {exc}"[:200],
                       "cells_executed": None, "runtime_s": None, "env": None,
                       "data_mode": None, "outputs": [], "legacy_retry": False,
                       "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            record(row, LEADERBOARD)
            if row["verdict"] == "ok":
                ok += 1
            else:
                failed += 1
            print(f"[{i}/{len(todo)}] {row['verdict']:<8} "
                  f"{row['repo']}/{row['artifact']}"
                  + (f"  ({row.get('error', '')[:50]})" if row.get("error") else ""))

    try:
        lb = LEADERBOARD.relative_to(ROOT)
    except ValueError:  # overridden (tests): tmp path outside the repo
        lb = LEADERBOARD
    print(f"\n{ok} ok, {failed} not-ok -> {lb}")
    return 0


def main() -> int:
    return main_with()


PROMPT_HEADER = """You port ONE external strategy artifact into our backtest
spec format. Accept the artifact's logic as fact — do not redesign it. Fill
the template below; every field is required (null where unknown, and log it
under ambiguities). If entry/exit cannot be a deterministic function of past
data, exit with status UNTESTABLE in verdict and stop.
meta.slug MUST be exactly the slug given in the payload.
Return ONLY YAML — no prose, no fences.

--- TEMPLATE ---
"""

REQUIRED_KEYS = ("meta", "data", "signal", "rules", "costs", "validation")

MAX_PROMPT_CHARS = 40_000


def repo_slug_safe(repo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")


def validate_spec(spec: dict) -> list[str]:
    """Contract checks a promoted spec must pass before it lands in specs/
    (backtest.py re-validates deeply at run time)."""
    errors = []
    for key in REQUIRED_KEYS:
        if key not in spec:
            errors.append(f"missing required section: {key}")
    if "costs" in spec and not spec["costs"]:
        errors.append("costs section is required and non-empty")
    if errors:
        return errors
    return [] if spec["meta"].get("slug") else ["meta.slug is required"]


def promote(repo: str, artifact: str, model: str | None = None,
            extra: list[str] | None = None) -> Path:
    """LLM-port one artifact into specs/ext-<repo>-<slug>.yaml. Spec-shaped
    artifacts are ingested directly; executed artifacts are ported from
    their content the same way (human reviews the diff before backtest)."""
    repo_dir = REPOS / repo.replace("/", "-")
    target = repo_dir / artifact
    if not target.exists():
        sys.exit(f"error: {artifact} not found in {repo_dir}")
    template = TEMPLATE.read_text()
    prompt = (
        f"{PROMPT_HEADER}\n{template}\n\n--- ARTIFACT ---\n"
        f"repo: {repo}\nslug_prefix: ext-{repo_slug_safe(repo)}-\n\n"
        f"{target.read_text(errors='ignore')[:MAX_PROMPT_CHARS]}\n"
    )
    reply = llm.complete(prompt, model=model, extra=extra, timeout=600)
    text = reply.strip()
    fence = re.search(r"```(?:yaml)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1)
    import yaml
    try:
        spec = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        sys.exit(f"error: unparseable spec reply: {exc}")
    stem = Path(artifact).stem
    expected_prefix = f"ext-{repo_slug_safe(repo)}-"
    if not str(spec.get("meta", {}).get("slug", "")).startswith(expected_prefix):
        sys.exit(f"error: meta.slug must start with {expected_prefix!r}")
    errors = validate_spec(spec)
    if errors:
        sys.exit(f"error: promoted spec failed validation: {'; '.join(errors)}")
    SPECS.mkdir(parents=True, exist_ok=True)
    out = SPECS / f"{spec['meta']['slug']}.yaml"
    tmp = out.with_suffix(".yaml.tmp")
    tmp.write_text(text + "\n")
    tmp.replace(out)
    return out


def promote_cli(ref: str, model: str | None, extra: list[str]) -> int:
    repo, _, artifact = ref.partition("/")
    if not artifact:
        sys.exit("error: --promote expects REPO/ARTIFACT")
    try:
        out = promote(repo, artifact, model=model, extra=extra)
    except llm.LLMError as exc:
        sys.exit(f"error: {exc}")
    print(f"promoted -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
