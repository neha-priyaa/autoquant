# External Strategy-Repo Lane — Design

**Date:** 2026-10-13
**Issues:** #22 (epic), #23, #24, #25, #26, #27
**Status:** Approved approach; spec for implementation planning

## Overview

A second ingestion lane alongside the article lane (harvest → fetch → triage →
extract → codegen → backtest). Instead of articles, we ingest GitHub repos that
already contain quantitative strategies (notebooks, scripts, spec-like text).
The lane contract, decided up front: **we accept repo content as fact** — we do
not validate or judge the repo's internal logic. Our only job is execution and
backtesting against **our data**, then promoting anything interesting into the
existing validated lane.

## Resolved decisions

| Question | Decision |
|---|---|
| Epic scope | One design spec, one 5-phase implementation plan (phase per sub-issue) |
| Isolation | Per-repo `uv` venvs. No Docker. |
| Network policy | Shim-forced offline: `PYTHONPATH` stubs of `yfinance` / `pandas_datareader` serve our `data/prices/` + `catalog.py` cache. Cache misses pre-fetch via `catalog.py` paths; unresolvable misses raise a clean `DataNotAvailable` recorded in the verdict. |
| Execution scale | Verdict-filtered: only artifacts triaged `RUN_WITH_OUR_DATA` or `RUN_BUNDLED_DATA` execute. `NEEDS_HEAVY_ENV` executes behind a `--heavy` flag. |
| Success metric | Ran-and-produced: leaderboard rows record verdict, runtime, env id, data mode, outputs. Comparable strategy numbers come later via promotion into the existing lane. |
| Legacy fallback env | Implemented: on a run failing with pandas/numpy API-error signatures and no repo pins, retry once in a legacy env (older Python + pandas 1.x pin set). Both attempts recorded. |

## Pipeline shape

```
harvest_repo.py    # [P1] shallow clone + inventory manifest -> data/repos/<owner>-<repo>/manifest.json
triage_repo.py     # [P2] LLM runnability scoring per artifact -> data/repo_triage.jsonl
repo_env.py        # [P3] module (no CLI): per-repo uv venv build/reuse keyed on (repo SHA, deps hash)
external_shim/     # [P4] package dir: yfinance/ + pandas_datareader/ stubs over our price cache
run_external.py    # [P5] execution harness -> results/external/<repo>/<artifact>.* + leaderboard + --promote
```

All stages follow existing conventions: flat root-level scripts, `main_with(argv)`
+ thin `main()`, module-level `ROOT`/path constants, resumability via
artifact-presence (no central state machine), atomic writes (tmp + `.replace()`,
or append-mode for jsonl), `print()` progress, per-item `try/except` that
records errors instead of crashing, ThreadPoolExecutor with `--jobs` where
per-item work is IO/LLM-bound, `llm.preflight()` + circuit breaker for LLM
stages.

## P1 — `harvest_repo.py` (issue #23)

**CLI:** `python3 harvest_repo.py <owner>/<repo> ... [--repos-file FILE] [--out data/repos]`

**Behavior:**
- `git clone --depth 1` into `data/repos/<owner>-<repo>/`; record pinned SHA
  (`git rev-parse HEAD` of the clone).
- Resumable: if the directory exists and manifest records the same SHA → skip.
  If SHA differs → re-clone (remove + fresh shallow clone).
- Walk the tree (skip `.git/`) and write `manifest.json`:

```jsonc
{
  "repo": "owner/name",
  "sha": "<40-hex>",
  "cloned_at": "<iso8601>",
  "notebooks":    [{"path": "...", "kernel": "...|null", "has_outputs": bool, "n_cells": int}],
  "scripts":      [{"path": "...", "has_main": bool, "n_lines": int}],   // has_main = "if __name__" found
  "spec_texts":   [{"path": "..."}],                                     // .yaml/.yml/.md strategy descriptions
  "data_files":   [{"path": "...", "bytes": int}],                       // csv/parquet/h5/pkl/pickle
  "deps":         {"requirements_txt": "path|null", "environment_yml": "path|null",
                   "setup_py": "path|null", "pyproject_toml": "path|null"}
}
```

- Spec-like detection: `.md`/`.yaml`/`.yml` files whose content mentions
  strategy-indicative terms (entry, signal, position, backtest, allocation) —
  cheap keyword gate, not LLM. LLM refines in P2.
- `data/repos/` is already covered by the `data/` gitignore rule.
- Manifest schema documented in the module docstring.

**Errors:** clone failure → recorded to `sys.stderr`, script continues with
other repos; nonzero exit only if all requested repos failed.

## P2 — `triage_repo.py` (issue #24)

**CLI:** `python3 triage_repo.py [--repo owner/name] [--limit N] [--jobs 4] [--model M] [--llm-arg A]... [--rescore]`

**Behavior:**
- Reads `data/repos/*/manifest.json` (optionally one repo), builds one LLM
  prompt per artifact via a new rubric file `repo_triage_prompt.md` (repo root,
  next to `triage_prompt.md`, same Role/Input/Rubric/Output-schema format).
- Prompt payload: artifact metadata + a content excerpt (truncated, ~40k chars,
  same convention as triage.py).
- Appends verdicts to `data/repo_triage.jsonl`, one row per artifact. Key =
  `(repo, artifact path)`; existing verdicts skipped unless `--rescore`.
- Verdict row schema:

```jsonc
{
  "repo": "owner/name",
  "sha": "<pinned sha at triage time>",
  "artifact": "relative/path",
  "kind": "notebook|script|spec_text",
  "verdict": "RUN_WITH_OUR_DATA|RUN_BUNDLED_DATA|NEEDS_HEAVY_ENV|SPEC_ARTIFACT|INTERACTIVE_ONLY|SKIP",
  "symbols": ["AAPL", "..."],
  "data_calls": ["yf.download", "pd.read_csv"],
  "heavy_deps": ["torch"],
  "runtime_class": "seconds|minutes|hours",
  "old_pandas": true,              // repo deps suggest pre-1.0/1.x pandas API
  "confidence": 0.0,
  "reason": "one line"
}
```

- Errors (LLM CLI failure, unparseable) → `{"repo", "artifact", "error"}`
  rows; retried on a later run. Circuit breaker per `llm.circuit_break`.
- LLM calls concurrent via ThreadPoolExecutor(`--jobs`).

## P3 — `repo_env.py` module (issue #25)

**No CLI.** Imported by `run_external.py`.

- `ensure_env(repo_dir, manifest, sha) -> EnvInfo`:
  - No declared deps → return the main project env marker (run under
    `uv run python` in the project root).
  - Deps declared → target `data/repos/<repo>/.venv`:
    `uv venv` then `uv pip install -r requirements.txt` (or `--reinstall` from
    `environment.yml` deps parsed to a requirements list; `setup.py`/
    `pyproject.toml`-only repos fall back to `pip install -e .` skipped — we
    install nothing and mark the env `UNSUPPORTED`, artifacts then triage to
    `SKIP` at execution time with that reason).
  - Reuse key: `hash(sha + deps-file content)`. Stored in
    `data/repos/<repo>/.env.json`; matching key → reuse, mismatch → rebuild.
  - ta-lib in the dep list → do not build; mark artifact `SKIP` (reason:
    system C library) at run time.
- `legacy_env(repo_dir) -> EnvInfo`: fallback venv `.venv-legacy`, older
  Python + pinned pandas 1.x / numpy<2 set, built on demand.
- No repo dependency ever touches the project `uv.lock` (all installs target
  the per-repo venv path with `--python <venv>`).

## P4 — `external_shim/` package (issue #26)

- `external_shim/yfinance/__init__.py` + `external_shim/pandas_datareader/__init__.py`.
- Exposed API subset (grows on evidence from pilot repos):
  - `yf.download(tickers, start=None, end=None, ...)` → DataFrame from our cache
  - `yf.Ticker(sym).history(start=..., end=..., ...)` → DataFrame
  - `pdr.DataReader(name, data_source, start, end)` → DataFrame
- Backing store: `data/prices/<ticker>.csv` first, then `catalog.py` yahoo
  series. Miss → pre-fetch through the existing catalog fetch path (bounded,
  offline-friendly tickers only) → still missing → raise `DataNotAvailable`
  (subclass of `Exception`, also exposed as `yf.DataNotAvailable` since some
  repos catch broad exceptions).
- Multi-ticker `download` returns the standard columned frame (or the
  multi-index frame when `group_by`/multiple tickers, matching yfinance shape).
- Launch convention: subprocess/nbclient kernel env gets
  `PYTHONPATH=<repo-root>/external_shim:<run-copy>` so the shim shadows any
  site-packages copy. Shim dir name must not collide with repo internals.
- `RUN_BUNDLED_DATA` mode: no shim on the path; run-copy of the repo keeps its
  own data files readable.
- Hard network kill (`unshare -n`) is Linux-only and **out of scope**; the
  shim is the enforcement mechanism on macOS.
- Original clone never mutated: execution always runs in a fresh run-copy
  `results/external/<repo>/runs/<artifact-stem>/` (repo files copied minus
  `.git/`), or the executed notebook is written to the results tree rather
  than in place.

## P5 — `run_external.py` (issue #27)

**CLI:** `python3 run_external.py [--repo owner/name] [--jobs 2] [--timeout 600] [--heavy] [--promote ARTIFACT]`

**Execution:**
- Pending = triage verdict ∈ {RUN_WITH_OUR_DATA, RUN_BUNDLED_DATA} (+
  NEEDS_HEAVY_ENV when `--heavy`) and no leaderboard row for `(repo, artifact,
  sha)` yet.
- Env via `repo_env.ensure_env`; data mode via verdict.
- Notebooks: `jupyter nbconvert --execute` (or `nbclient`) in the per-repo
  env's python, per-cell timeout `--timeout`, executed notebook saved to
  `results/external/<repo>/<artifact-stem>.ipynb` with inline outputs.
- Scripts: isolated subprocess (`start_new_session=True`, process-group kill
  on timeout — same pattern as backtest_batch.py), cwd = run-copy, env =
  per-repo venv + shim PYTHONPATH.
- Spec artifacts: never executed.

**Leaderboard:** `results/external/leaderboard.jsonl`, append-only, one row per
attempt:

```jsonc
{
  "repo": "owner/name", "sha": "...", "artifact": "path",
  "kind": "notebook|script", "verdict": "ok|error|timeout|skip",
  "cells_executed": 12,            // notebooks; null for scripts
  "runtime_s": 43.2,
  "env": "venv|venv-legacy|main|none",
  "data_mode": "ours|bundled",
  "outputs": ["...ipynb", "..."],  // evidence files produced
  "error": "first line of stderr|null",
  "legacy_retry": false,           // true when fallback env was used
  "run_at": "<iso8601>"
}
```

**Promotion (`--promote <repo>/<artifact>`):** manual-trigger. For
`SPEC_ARTIFACT`s: direct ingestion — LLM pass maps the text onto
`specs/ext-<repo>-<slug>.yaml` against `_TEMPLATE.yaml` (reuses extract
patterns; validated by `backtest.py` smoke rules). For executed artifacts: an
LLM-reviewed port from the executed notebook/script into the same spec form.
Batch promotion deferred.

## Error handling

Every stage: per-item failure recorded (jsonl error row / marker), run
continues; summary printed at end; fatal config problems `sys.exit` early.
Execution failures produce leaderboard `error`/`timeout` rows with the first
stderr line — never a crash of the batch.

## Testing

Follow existing conventions: flat `tests/test_<module>.py` per source module,
`tmp_path` + `monkeypatch` fixtures, LLM mocked by monkeypatching
`llm.subprocess.run` (and, for execution, `subprocess.run` of the harness).

- P1: manifest schema against a tiny fixture repo dir built in `tmp_path`
  (no network); clone faked by monkeypatching `subprocess.run`; SHA-skip logic.
- P2: prompt build, verdict parse, resumability, circuit breaker.
- P3: cache-key reuse/rebuild logic (uv calls monkeypatched); ta-lib skip.
- P4: shim `download`/`history`/`DataReader` against a fake price cache;
  cache-miss → `DataNotAvailable`; column shapes.
- P5: pending-selection filter, timeout kill, leaderboard row contract,
  `--promote` spec generation passes the existing smoke validation.

Suite: `uv run python -m pytest`.

## Out of scope

- Docker / container isolation; `unshare -n` hard-offline (Linux-only).
- Batch/automatic promotion.
- Extracting comparable performance numbers from executed notebooks.
- Judging strategy validity of external content (lane contract).
