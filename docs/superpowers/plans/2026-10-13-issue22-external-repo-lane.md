# External Strategy-Repo Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a second ingestion lane that shallow-clones GitHub strategy repos, triages their artifacts for runnability, builds per-repo envs, executes them offline against our price cache via import shims, and records results in an external leaderboard with manual promotion into `specs/`.

**Architecture:** Five stages mirroring the article lane's conventions (flat scripts, `main_with(argv)`, artifact-is-state resumability, atomic writes, ThreadPoolExecutor): `harvest_repo.py` → `triage_repo.py` → `repo_env.py` (module) + `external_shim/` (PYTHONPATH package) → `run_external.py`. Spec: `docs/superpowers/specs/2026-10-13-external-repo-lane-design.md`.

**Tech Stack:** Python 3.11+, git CLI (`--depth 1`), `uv venv`/`uv pip`, pandas, nbconvert+ipykernel (installed into repo venvs, never project), existing `llm.py` adapter, pytest.

**Branch:** `issue22-external-repo-lane` (already created; spec committed).

---

## File structure

| File | Responsibility |
|---|---|
| `harvest_repo.py` | P1: shallow-clone repos → `data/repos/<owner>-<repo>/{tree, manifest.json}` |
| `tests/test_harvest_repo.py` | P1 tests (no network; clone monkeypatched) |
| `repo_triage_prompt.md` | P2 LLM rubric: runnability verdict enum + JSON schema |
| `triage_repo.py` | P2: LLM scoring per artifact → `data/repo_triage.jsonl` |
| `tests/test_triage_repo.py` | P2 tests (llm monkeypatched) |
| `repo_env.py` | P3 module: per-repo uv venv build/reuse, legacy fallback, ta-lib guard |
| `tests/test_repo_env.py` | P3 tests (uv calls monkeypatched) |
| `external_shim/_aqdata.py` | P4 shared cache-serving code (self-contained; runs in repo venvs) |
| `external_shim/yfinance/__init__.py` | P4 `yf.download` / `Ticker.history` shim |
| `external_shim/pandas_datareader/__init__.py` | P4 `DataReader` shim |
| `tests/test_external_shim.py` | P4 tests (loads shims via sys.path) |
| `run_external.py` | P5 harness: pending selection, run-copies, execution, leaderboard, `--promote` |
| `tests/test_run_external.py` | P5 tests |
| `README.md` | Pipeline diagram + usage lines (final task) |

Conventions used throughout (match existing code — read `triage.py`, `backtest_batch.py` before starting): `ROOT = Path(__file__).resolve().parent`; `main_with(argv) -> int` + thin `main()`; `if __name__ == "__main__": raise SystemExit(main())`; plain-dict rows; `print()` progress; per-item try/except; `start_new_session=True` + process-group SIGKILL on timeout.

---

## Phase 1 — `harvest_repo.py` (issue #23)

### Task 1: Manifest scanning (pure functions)

**Files:**
- Create: `harvest_repo.py`
- Create: `tests/test_harvest_repo.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_harvest_repo.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_harvest_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'harvest_repo'`

- [ ] **Step 3: Write the implementation**

```python
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
                            "n_lines": text.count("\n") + 1})
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_harvest_repo.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add harvest_repo.py tests/test_harvest_repo.py
git commit -m "feat: harvest_repo manifest scanning (#23)"
```

### Task 2: Clone orchestration + CLI

**Files:**
- Modify: `harvest_repo.py`
- Modify: `tests/test_harvest_repo.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_harvest_repo.py`)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_harvest_repo.py -v -k "HarvestOne or MainWith"`
Expected: FAIL — `AttributeError: module 'harvest_repo' has no attribute 'main_with'`

- [ ] **Step 3: Write the implementation** (append to `harvest_repo.py`)

```python
def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="*", metavar="OWNER/REPO",
                    help="GitHub repos to clone and inventory")
    ap.add_argument("--repos-file", type=Path, default=None,
                    help="file with one OWNER/REPO per line")
    ap.add_argument("--out", type=Path, default=REPOS)
    args = ap.parse_args(argv)

    repos = list(args.repos)
    if args.repos_file:
        repos += [line.strip() for line in
                  args.repos_file.read_text().splitlines() if line.strip()]
    if not repos:
        sys.exit("error: give OWNER/REPO args or --repos-file")

    args.out.mkdir(parents=True, exist_ok=True)
    ok = skip = failed = 0
    for repo in repos:
        status, detail = harvest_one(repo, args.out)
        print(detail)
        if status == "ok":
            ok += 1
        elif status == "skip":
            skip += 1
        else:
            failed += 1
            print(detail, file=sys.stderr)
    print(f"\n{ok} cloned, {skip} skipped, {failed} failed -> {args.out}")
    return 1 if failed == len(repos) else 0


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_harvest_repo.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add harvest_repo.py tests/test_harvest_repo.py
git commit -m "feat: harvest_repo clone orchestration + CLI (#23)"
```

---

## Phase 2 — `triage_repo.py` (issue #24)

### Task 3: Prompt rubric + artifact helpers

**Files:**
- Create: `repo_triage_prompt.md`
- Create: `triage_repo.py`
- Create: `tests/test_triage_repo.py`

- [ ] **Step 1: Write the rubric** (`repo_triage_prompt.md`)

````markdown
# Repo Artifact Triage Rubric

## Role

You score whether ONE artifact from a third-party strategy repo can be
EXECUTED against our local price cache. You judge runnability only. You do
NOT judge whether the strategy is sensible — the lane accepts repo content
as fact.

## Input

You receive a JSON payload with: `repo`, `sha`, `artifact` (path within the
repo), `kind` (`notebook` | `script` | `spec_text`), `deps` (the repo's
declared-dependency files, verbatim, truncated), and `text` (the artifact's
content, possibly truncated).

## Verdict enum — exactly one of

- `RUN_WITH_OUR_DATA` — executes and its data needs can be served from our
  price cache (yfinance/pandas_datareader calls on ordinary symbols).
- `RUN_BUNDLED_DATA` — executes and reads the repo's own bundled data files.
- `NEEDS_HEAVY_ENV` — needs torch / tensorflow / gym / similar heavy deps.
- `SPEC_ARTIFACT` — text/yaml describing a strategy with no executable code;
  routed to promotion, never executed.
- `INTERACTIVE_ONLY` — requires widgets, plotly dashboards, manual cells, or
  user input; cannot run headless.
- `SKIP` — anything else (ta-lib C dependency, dead links, data behind
  logins, indecipherable content).

## Fields to assess

- `symbols`: ticker symbols the code requests (uppercase, best effort, []).
- `data_calls`: loading calls found, e.g. ["yf.download", "pd.read_csv"].
- `heavy_deps`: heavy libraries imported (torch, tensorflow, gym, ta-lib...).
- `runtime_class`: "seconds" | "minutes" | "hours" (RL training loops = hours).
- `old_pandas`: true when deps (or the code's API usage) suggest a pandas
  0.x/1.x-era API that may not run on pandas 2.x.
- `confidence`: 0.0-1.0 that your verdict is right.
- `reason`: one line.

## Output

Return ONLY the JSON object — no prose, no markdown fences:

```json
{
  "verdict": "RUN_WITH_OUR_DATA",
  "symbols": [],
  "data_calls": [],
  "heavy_deps": [],
  "runtime_class": "seconds",
  "old_pandas": false,
  "confidence": 0.8,
  "reason": ""
}
```

## Non-negotiable rules

- One verdict per artifact. Never merge artifacts.
- If `text` is unreadable or empty, verdict is `SKIP` with low confidence.
- `ta-lib` in heavy_deps => verdict `SKIP` (system C library we do not build).
- `.md`/`.yaml` files with strategy prose but no runnable code =>
  `SPEC_ARTIFACT`, even if a notebook could express the same idea.
````

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_triage_repo.py
"""Tests for triage_repo.py — llm is monkeypatched, no network."""
import json
from pathlib import Path

import triage_repo as tr


MANIFEST = {
    "repo": "o/r", "sha": "a" * 40,
    "notebooks": [{"path": "n.ipynb", "kernel": "python3", "has_outputs": False, "n_cells": 3}],
    "scripts": [{"path": "s.py", "has_main": True, "n_lines": 10}],
    "spec_texts": [{"path": "idea.md"}],
    "data_files": [{"path": "d.csv", "bytes": 10}],
    "deps": {"requirements_txt": "requirements.txt"},
}


class TestArtifacts:
    def test_every_executable_kind_listed(self):
        arts = tr.artifacts(MANIFEST)
        assert [(a["kind"], a["path"]) for a in arts] == [
            ("notebook", "n.ipynb"), ("script", "s.py"), ("spec_text", "idea.md")]

    def test_empty_manifest(self):
        assert tr.artifacts({}) == []


class TestExcerpt:
    def test_notebook_cells_joined(self, tmp_path):
        (tmp_path / "n.ipynb").write_text(json.dumps(
            {"cells": [{"cell_type": "code", "outputs": [], "source": ["import yfinance as yf\n",
                                                                   "yf.download('AAPL')"]}]}))
        text = tr.excerpt(tmp_path, "n.ipynb")
        assert "yf.download('AAPL')" in text
        assert '"cell_type"' not in text  # sources, not the raw json envelope

    def test_plain_text_truncated(self, tmp_path):
        (tmp_path / "s.py").write_text("x = 1\n" * 50_000)
        text = tr.excerpt(tmp_path, "s.py")
        assert len(text) <= tr.MAX_CHARS + 40  # truncation marker allowed
        assert text.endswith("[...truncated for length...]")


class TestBuildPrompt:
    def test_rubric_then_payload(self, tmp_path):
        (tmp_path / "s.py").write_text("import pandas\n")
        prompt = tr.build_prompt("RUBRIC", MANIFEST, tmp_path, {"path": "s.py", "kind": "script"})
        assert prompt.startswith("RUBRIC")
        payload = json.loads(prompt[prompt.rindex("{\n  \"repo\""):]) if False else None
        assert '"repo": "o/r"' in prompt or '"repo":"o/r"' in json.dumps(
            json.loads(prompt.split("Return ONLY the JSON object")[-1]), default=str)
```

Hmm — that last test is awkward. Replace `TestBuildPrompt` with:

```python
class TestBuildPrompt:
    def test_rubric_then_parseable_payload(self, tmp_path):
        (tmp_path / "s.py").write_text("import pandas\n")
        prompt = tr.build_prompt("RUBRIC", MANIFEST, tmp_path,
                                 {"path": "s.py", "kind": "script"})
        assert prompt.startswith("RUBRIC")
        payload_text = prompt[prompt.rindex("\n{\n"):]
        payload = json.loads(payload_text)
        assert payload["repo"] == "o/r"
        assert payload["artifact"] == "s.py"
        assert payload["kind"] == "script"
        assert "import pandas" in payload["text"]

    def test_deps_verbatim_in_payload(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pandas==1.3.0\n")
        prompt = tr.build_prompt("RUBRIC", MANIFEST, tmp_path,
                                 {"path": "s.py", "kind": "script"})
        payload = json.loads(prompt[prompt.rindex("\n{\n"):])
        assert "pandas==1.3.0" in payload["deps_text"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_triage_repo.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'triage_repo'`

- [ ] **Step 4: Write the implementation** (`triage_repo.py`)

```python
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
        f"{json.dumps(payload, ensure_ascii=False)}\n"
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_triage_repo.py -v`
Expected: PASS — but `TestExcerpt.test_plain_text_truncated` asserts `tr.MAX_CHARS`; if the import of `triage` (which reads no files at import time) is fine, all pass.

- [ ] **Step 6: Commit**

```bash
git add repo_triage_prompt.md triage_repo.py tests/test_triage_repo.py
git commit -m "feat: triage_repo rubric + prompt builders (#24)"
```

### Task 4: Scoring + CLI

**Files:**
- Modify: `triage_repo.py`
- Modify: `tests/test_triage_repo.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
VERDICT = json.dumps({
    "verdict": "RUN_WITH_OUR_DATA", "symbols": ["AAPL"],
    "data_calls": ["yf.download"], "heavy_deps": [],
    "runtime_class": "seconds", "old_pandas": False,
    "confidence": 0.9, "reason": "simple yf.download usage",
})


class TestScoreOne:
    def _setup_repo(self, tmp_path):
        (tmp_path / "s.py").write_text("import pandas\n")
        manifest = dict(MANIFEST, sha="a" * 40)
        return manifest

    def test_ok(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: VERDICT)
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row["verdict"] == "RUN_WITH_OUR_DATA"
        assert row["repo"] == "o/r" and row["artifact"] == "s.py"
        assert row["sha"] == "a" * 40
        assert "error" not in row

    def test_llm_error_recorded(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)

        def boom(*a, **k):
            raise tr.llm.LLMError("CLI timed out after 300s")
        monkeypatch.setattr(tr.llm, "complete", boom)
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row == {"repo": "o/r", "artifact": "s.py",
                       "error": "CLI timed out after 300s"}

    def test_unparseable_reply(self, tmp_path, monkeypatch):
        manifest = self._setup_repo(tmp_path)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: "no json here")
        row = tr.score_one(manifest, tmp_path, {"path": "s.py", "kind": "script"},
                           "RUBRIC", model=None, extra=[])
        assert row["error"].startswith("unparseable reply")


class TestMainWith:
    def test_scores_pending_and_resumes(self, tmp_path, monkeypatch):
        repos = tmp_path / "repos" / "o-r"
        repos.mkdir(parents=True)
        (repos / "s.py").write_text("import pandas\n")
        (repos / "manifest.json").write_text(json.dumps(MANIFEST))
        monkeypatch.setattr(tr, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(tr, "TRIAGE", tmp_path / "repo_triage.jsonl")
        monkeypatch.setattr(tr, "PROMPT", Path(tr.__file__).parent / "repo_triage_prompt.md")
        monkeypatch.setattr(tr.llm, "preflight", lambda: None)
        monkeypatch.setattr(tr.llm, "complete", lambda *a, **k: VERDICT)

        assert tr.main_with(["--repo", "o/r"]) == 0
        rows = [json.loads(l) for l in
                (tmp_path / "repo_triage.jsonl").read_text().splitlines()]
        assert {r["artifact"] for r in rows} == {"n.ipynb", "s.py", "idea.md"}

        # re-run is a no-op
        calls = []
        monkeypatch.setattr(tr.llm, "complete",
                            lambda *a, **k: calls.append(1) or VERDICT)
        assert tr.main_with(["--repo", "o/r"]) == 0
        assert calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_triage_repo.py -v -k "TestScoreOne or TestMainWith"`
Expected: FAIL — `AttributeError: ... no attribute 'score_one'`

- [ ] **Step 3: Write the implementation** (append to `triage_repo.py`)

```python
def score_one(manifest: dict, repo_dir: Path, artifact: dict, rubric: str,
              model: str | None = None, extra: list[str] | None = None) -> dict:
    key = {"repo": manifest["repo"], "artifact": artifact["path"]}
    prompt = build_prompt(rubric, manifest, repo_dir, artifact)
    try:
        reply = llm.complete(prompt, model=model, extra=extra, timeout=CLI_TIMEOUT)
    except llm.LLMError as exc:
        return {**key, "error": str(exc)}
    try:
        result = parse_json(reply)
    except (ValueError, json.JSONDecodeError) as exc:
        return {**key, "error": f"unparseable reply: {exc}"[:300]}
    result.update(key)
    result["sha"] = manifest.get("sha")
    return result


def _verdict_key(row: dict) -> str:
    return f"{row.get('repo')}/{row.get('artifact')}"


def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None, help="score only OWNER/REPO")
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit")
    ap.add_argument("--jobs", type=int, default=4, help="concurrent LLM calls")
    ap.add_argument("--model", default=None)
    ap.add_argument("--llm-arg", action="append", default=[], metavar="ARG")
    ap.add_argument("--rescore", action="store_true",
                    help="re-score artifacts already in repo_triage.jsonl")
    args = ap.parse_args(argv)

    try:
        llm.preflight()
    except llm.LLMError as exc:
        sys.exit(f"error: {exc}")

    rubric = PROMPT.read_text()
    scored = load(TRIAGE)
    seen = set() if args.rescore else {_verdict_key(r) for r in scored}

    todo: list[tuple[dict, Path, dict]] = []
    manifests = sorted(REPOS.glob("*/manifest.json"))
    if args.repo:
        manifests = [m for m in manifests
                     if m.parent.name == args.repo.replace("/", "-")]
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text())
        repo_dir = manifest_path.parent
        for artifact in artifacts(manifest):
            if _verdict_key({"repo": manifest["repo"],
                             "artifact": artifact["path"]}) not in seen:
                todo.append((manifest, repo_dir, artifact))
    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("nothing to triage -- run harvest_repo.py first, or pass --rescore")
        return 0

    print(f"triaging {len(todo)} artifacts ({args.jobs} at a time)\n")
    results: list[dict] = []
    abort = None
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(score_one, m, d, a, rubric, args.model,
                               args.llm_arg): a for m, d, a in todo}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            res = fut.result()
            results.append(res)
            if "error" in res:
                print(f"[{i}/{len(todo)}] ERR  {res['error'][:60]}  "
                      f"{res.get('repo')}/{res.get('artifact')}")
            else:
                print(f"[{i}/{len(todo)}] {res.get('verdict', '?'):<18} "
                      f"{res['repo']}/{res['artifact']}")
            abort = llm.circuit_break(results)
            if abort:
                pool.shutdown(wait=False, cancel_futures=True)
                break

    fresh = {_verdict_key(r) for r in results}
    save(TRIAGE, [r for r in scored if _verdict_key(r) not in fresh] + results)

    if abort:
        print(f"\n{abort}")
        return 1
    counts: dict[str, int] = {}
    for r in results:
        counts[r.get("verdict", "error")] = counts.get(r.get("verdict", "error"), 0) + 1
    print("\nverdicts:", ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"verdicts -> {TRIAGE.relative_to(ROOT)}")
    return 0


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: `from triage import load, parse_json, save` — those helpers exist in `triage.py:42-51,74-87` and take/return the same shapes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_triage_repo.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add triage_repo.py tests/test_triage_repo.py
git commit -m "feat: triage_repo scoring + resumable CLI (#24)"
```

---

## Phase 3 — `repo_env.py` (issue #25)

### Task 5: Env selection + uv venv build/reuse

**Files:**
- Create: `repo_env.py`
- Create: `tests/test_repo_env.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_repo_env.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_repo_env.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'repo_env'`

- [ ] **Step 3: Write the implementation** (`repo_env.py`)

```python
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
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOS = ROOT / "data" / "repos"

# Notebook execution support, installed into every repo venv (never project).
EXEC_DEPS = ["nbconvert", "ipykernel"]

# Fallback env: older interpreter + pandas 1.x-era pin set (issue #25).
LEGACY_PYTHON = "3.9"
LEGACY_PINS = ["pandas<1.4", "numpy<1.24", "matplotlib"] + EXEC_DEPS

HEAVY_MARKERS = ("ta-lib", "talib")


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    return proc.returncode, (proc.stderr or proc.stdout)[-300:]


def _state_path(repo_dir: Path) -> Path:
    return repo_dir / ".env.json"


def _deps_paths(repo_dir: Path, manifest: dict) -> list[Path]:
    out = []
    for key in ("requirements_txt", "environment_yml", "setup_py", "pyproject_toml"):
        rel = manifest.get("deps", {}).get(key)
        if rel and (repo_dir / rel).exists():
            out.append(repo_dir / rel)
    return out


def _env_key(repo_dir: Path, manifest: dict, deps_paths: list[Path]) -> str:
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


def build_env(repo_dir: Path, manifest: dict, deps_paths: list[Path]) -> dict:
    venv = repo_dir / ".venv"
    python = venv / "bin" / "python"
    rc, err = _run(["uv", "venv", str(venv)])
    if rc != 0:
        return {"env": "unsupported", "reason": f"uv venv failed: {err}"}
    requirements = repo_dir / manifest["deps"]["requirements_txt"]
    rc, err = _pip_install(python, ["-r", str(requirements), *EXEC_DEPS])
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

    key = _env_key(repo_dir, manifest, deps_paths)
    state_path = _state_path(repo_dir)
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text())
            if state.get("key") == key and state.get("env") == "venv":
                return state
        except (json.JSONDecodeError, OSError):
            pass

    info = build_env(repo_dir, manifest, deps_paths)
    if info["env"] == "venv":
        info["key"] = key
        state_path.write_text(json.dumps(info) + "\n")
    return info
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_repo_env.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add repo_env.py tests/test_repo_env.py
git commit -m "feat: repo_env per-repo uv venv builder (#25)"
```

### Task 6: Legacy fallback env + pin detection

**Files:**
- Modify: `repo_env.py`
- Modify: `tests/test_repo_env.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_repo_env.py -v -k Legacy`
Expected: FAIL — `AttributeError: ... no attribute 'legacy_env'`

- [ ] **Step 3: Write the implementation** (append to `repo_env.py`)

```python
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
    state_path.write_text(json.dumps(info) + "\n")
    return info


def has_pins(deps_text: str) -> bool:
    """True when any dependency declares a version constraint."""
    return any(op in deps_text for op in ("==", ">=", "<=", "~=", "!=", ">", "<"))


LEGACY_MARKERS = ("has no attribute", "unexpected keyword", "removed in",
                  "not a function", "cannot import name")


def legacy_worth_retry(error: str, env_used: str, has_pins: bool) -> bool:
    """Retry in the legacy env only when: the failure looks like a
    pandas/numpy API mismatch, the repo declared no pins, and we have not
    already retried there."""
    if env_used != "main" or has_pins:
        return False
    return any(m in error for m in LEGACY_MARKERS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_repo_env.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add repo_env.py tests/test_repo_env.py
git commit -m "feat: repo_env legacy fallback env + pin detection (#25)"
```

---

## Phase 4 — `external_shim/` (issue #26)

### Task 7: `_aqdata` cache server

**Files:**
- Create: `external_shim/_aqdata.py`
- Create: `tests/test_external_shim.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_external_shim.py
"""Tests for the external_shim packages. The shims are loaded by putting
external_shim/ first on sys.path (exactly how run_external.py injects them),
so 'import yfinance' resolves to the shim, not the real package."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
SHIM = str(ROOT / "external_shim")

Prices = pd.DataFrame(
    {"open": [1.0, 2.0], "high": [1.5, 2.5], "low": [0.5, 1.5],
     "close": [1.2, 2.2], "volume": [100, 200]},
    index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"]))


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    prices = tmp_path / "data" / "prices"
    prices.mkdir(parents=True)
    Prices.to_csv(prices / "AAPL.csv")
    cat = tmp_path / "data" / "catalog"
    cat.mkdir(parents=True)
    pd.DataFrame({"close": [3.0, 3.1]},
                 index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"])
                 ).to_csv(cat / "fred_DGS10.csv")
    monkeypatch.setenv("AUTOQUANT_DATA_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def shims(data_root):
    """Import the shim packages fresh, with external_shim/ front of sys.path."""
    saved_path = sys.path[:]
    saved_mods = {k: sys.modules.pop(k) for k in
                  ("yfinance", "pandas_datareader", "_aqdata") if k in sys.modules}
    sys.path.insert(0, SHIM)
    import yfinance
    import pandas_datareader
    import _aqdata
    yield {"yfinance": yfinance, "pandas_datareader": pandas_datareader,
           "_aqdata": _aqdata}
    sys.path[:] = saved_path
    for k in ("yfinance", "pandas_datareader", "_aqdata"):
        sys.modules.pop(k, None)
    sys.modules.update(saved_mods)


class TestDataNotAvailable:
    def test_unknown_symbol(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("MSFT")

    def test_unset_data_root(self, monkeypatch, shims):
        monkeypatch.delenv("AUTOQUANT_DATA_ROOT")
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("AAPL")

    def test_range_miss(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["_aqdata"].frame_for("AAPL", "2025-01-01", "2025-12-31")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_external_shim.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '_aqdata'`

- [ ] **Step 3: Write the implementation** (`external_shim/_aqdata.py`)

```python
"""Shared cache-serving code for the yfinance / pandas_datareader shims.

Deliberately self-contained: it runs inside external repos' venvs where only
pandas is guaranteed — no project imports. The served data root comes from
AUTOQUANT_DATA_ROOT (set by run_external.py):

    <root>/data/prices/<SYMBOL>.csv       legacy per-ticker cache
    <root>/data/catalog/<source>_<id>.csv catalog cache (catalog.py)

Prefetching happens in the parent harness (run_external.py warms
catalog.load for the triaged symbols); this shim only serves what is on
disk and raises DataNotAvailable on a miss — a recorded, actionable verdict
rather than a hang or a live fetch.
"""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


class DataNotAvailable(Exception):
    """Requested symbol/date-range is not in our cache."""


def data_root() -> Path:
    root = os.environ.get("AUTOQUANT_DATA_ROOT")
    if not root:
        raise DataNotAvailable(
            "AUTOQUANT_DATA_ROOT is not set -- the shim only serves a "
            "configured data root")
    return Path(root)


def _candidates(symbol: str, source: str) -> list[Path]:
    root = data_root()
    safe = symbol.replace("/", "_")
    out = [root / "data" / "prices" / f"{safe}.csv"]
    if source != "yahoo":
        out.insert(0, root / "data" / "catalog" / f"{source}_{safe}.csv")
    else:
        out.append(root / "data" / "catalog" / f"yahoo_{safe}.csv")
    return out


def frame_for(symbol: str, start=None, end=None, source: str = "yahoo") -> pd.DataFrame:
    """Normalized frame: lowercase columns, ascending DatetimeIndex (naive),
    filtered to [start, end]. Non-empty after filtering, else DataNotAvailable."""
    for path in _candidates(symbol, source):
        if not path.exists():
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        df.columns = [str(c).lower() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        try:
            df.index = df.index.tz_localize(None)
        except (TypeError, AttributeError):
            pass
        df = df.sort_index()
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        if df.empty:
            raise DataNotAvailable(
                f"{symbol}: cached data does not cover [{start}, {end}]")
        return df
    raise DataNotAvailable(
        f"{symbol}: not in the price cache -- the harness pre-fetches triaged "
        f"symbols; add it to the cache and re-run")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_external_shim.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add external_shim/_aqdata.py tests/test_external_shim.py
git commit -m "feat: external_shim cache server core (#26)"
```

### Task 8: `yfinance` shim

**Files:**
- Create: `external_shim/yfinance/__init__.py`
- Modify: `tests/test_external_shim.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
class TestYFinance:
    def test_download_single(self, shims):
        df = shims["yfinance"].download("AAPL", start="2020-01-01")
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]
        assert len(df) == 2

    def test_download_multi_returns_multiindex(self, shims, data_root):
        Prices.to_csv(data_root / "data" / "prices" / "MSFT.csv")
        panel = shims["yfinance"].download(["AAPL", "MSFT"])
        assert isinstance(panel.columns, pd.MultiIndex)
        assert set(panel.columns.get_level_values(0)) == {"AAPL", "MSFT"}

    def test_download_miss_raises_clean(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["yfinance"].download("ZZZZZ")

    def test_ticker_history(self, shims):
        df = shims["yfinance"].Ticker("AAPL").history(start="2020-01-01",
                                                      end="2020-01-31")
        assert len(df) == 2
        assert "close" in df.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_external_shim.py -v -k TestYFinance`
Expected: FAIL — `AttributeError: module 'yfinance' has no attribute 'download'` (or import error)

- [ ] **Step 3: Write the implementation** (`external_shim/yfinance/__init__.py`)

```python
"""yfinance shim — serves the project price cache (issue #26).

Injected via PYTHONPATH=external_shim so `import yfinance` resolves here in
external code. Supported subset, on evidence from the pilot repos:

    yf.download(ticker | [tickers], start=, end=, ...)  -> DataFrame
        single ticker: flat lowercase ohlcv frame
        list: MultiIndex columns (ticker, field)
    yf.Ticker(sym).history(period=, start=, end=, ...)  -> DataFrame

Everything else (downloaders, search, screener, crawl) raises
DataNotAvailable or AttributeError — loud and recorded, never a live fetch.
"""
from __future__ import annotations

import pandas as pd
from _aqdata import DataNotAvailable, frame_for  # noqa: F401

__all__ = ["DataNotAvailable", "download", "Ticker"]

FIELDS = ["open", "high", "low", "close", "volume"]


def _frame(symbol: str, start=None, end=None) -> pd.DataFrame:
    df = frame_for(symbol, start, end)
    cols = [c for c in FIELDS if c in df.columns]
    if not cols:
        raise DataNotAvailable(f"{symbol}: no ohlcv columns in cached data")
    return df[cols]


def download(tickers, start=None, end=None, *, auto_adjust=True,
             progress=False, group_by="column", **kwargs):
    single = isinstance(tickers, str)
    names = [tickers] if single else list(tickers)
    frames = {t: _frame(t, start, end) for t in names}
    if single:
        return frames[names[0]]
    return pd.concat(frames, axis=1, names=["ticker", "field"])


class Ticker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period="max", interval="1d", start=None, end=None, **kwargs):
        return _frame(self.symbol, start, end)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_external_shim.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add external_shim/yfinance/__init__.py tests/test_external_shim.py
git commit -m "feat: yfinance shim over the price cache (#26)"
```

### Task 9: `pandas_datareader` shim

**Files:**
- Create: `external_shim/pandas_datareader/__init__.py`
- Modify: `tests/test_external_shim.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
class TestPandasDatareader:
    def test_fred_datareader(self, shims):
        df = shims["pandas_datareader"].DataReader("DGS10", "fred")
        assert list(df.columns) == ["close"]
        assert len(df) == 2

    def test_default_source_is_yahoo(self, shims):
        df = shims["pandas_datareader"].DataReader("AAPL")
        assert len(df) == 2

    def test_unknown_source_raises(self, shims):
        with pytest.raises(shims["_aqdata"].DataNotAvailable):
            shims["pandas_datareader"].DataReader("X", "av-daily")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_external_shim.py -v -k TestPandasDatareader`
Expected: FAIL

- [ ] **Step 3: Write the implementation** (`external_shim/pandas_datareader/__init__.py`)

```python
"""pandas_datareader shim — DataReader over the project cache (issue #26).

Supported data_sources: "yahoo" (default), "fred", "stooq" — the sources
catalog.py caches. Anything else raises DataNotAvailable: recorded, never a
live fetch.
"""
from __future__ import annotations

from _aqdata import DataNotAvailable, frame_for  # noqa: F401

__all__ = ["DataNotAvailable", "DataReader"]

SOURCES = ("yahoo", "fred", "stooq")


def DataReader(name, data_source=None, start=None, end=None, **kwargs):
    if isinstance(name, (list, tuple)):
        return {n: DataReader(n, data_source, start, end, **kwargs) for n in name}
    source = data_source or "yahoo"
    if source not in SOURCES:
        raise DataNotAvailable(
            f"data_source {data_source!r} not shimmed (known: {', '.join(SOURCES)})")
    return frame_for(str(name), start, end, source=source)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_external_shim.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add external_shim/pandas_datareader/__init__.py tests/test_external_shim.py
git commit -m "feat: pandas_datareader shim over the cache (#26)"
```

---

## Phase 5 — `run_external.py` (issue #27)

### Task 10: Pending selection + leaderboard plumbing

**Files:**
- Create: `run_external.py`
- Create: `tests/test_run_external.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_run_external.py
"""Tests for run_external.py — subprocess/llm calls are monkeypatched."""
import json
from pathlib import Path

import run_external as rx


def verdict(v="RUN_WITH_OUR_DATA", repo="o/r", artifact="s.py",
            sha="a" * 40, **kw):
    return {"repo": repo, "artifact": artifact, "sha": sha, "verdict": v,
            "kind": "script", "symbols": ["AAPL"], "data_calls": [], **kw}


class TestPending:
    def test_executable_verdicts_only(self):
        rows = [verdict("RUN_WITH_OUR_DATA", artifact="a.py"),
                verdict("SPEC_ARTIFACT", artifact="b.md"),
                verdict("INTERACTIVE_ONLY", artifact="c.ipynb"),
                verdict("RUN_BUNDLED_DATA", artifact="d.py")]
        pend = rx.pending(rows, done=set(), heavy=False)
        assert [p["artifact"] for p in pend] == ["a.py", "d.py"]

    def test_heavy_needs_flag(self):
        rows = [verdict("NEEDS_HEAVY_ENV")]
        assert rx.pending(rows, done=set(), heavy=False) == []
        assert len(rx.pending(rows, done=set(), heavy=True)) == 1

    def test_already_done_skipped(self):
        rows = [verdict()]
        done = {("o/r", "s.py", "a" * 40)}
        assert rx.pending(rows, done=done, heavy=False) == []


class TestLeaderboard:
    def test_done_keys(self, tmp_path):
        lb = tmp_path / "leaderboard.jsonl"
        lb.write_text(json.dumps({"repo": "o/r", "artifact": "s.py",
                                  "sha": "a" * 40}) + "\n"
                      + "not json\n")
        assert rx.done_keys(lb) == {("o/r", "s.py", "a" * 40)}

    def test_record_appends(self, tmp_path):
        lb = tmp_path / "lb.jsonl"
        rx.record({"repo": "o/r", "verdict": "ok"}, lb)
        rx.record({"repo": "o/r", "verdict": "error"}, lb)
        assert len(lb.read_text().splitlines()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_run_external.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation** (`run_external.py`)

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_run_external.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add run_external.py tests/test_run_external.py
git commit -m "feat: run_external pending selection + leaderboard (#27)"
```

### Task 11: Prefetch, run-copies, script execution

**Files:**
- Modify: `run_external.py`
- Modify: `tests/test_run_external.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
class TestPrefetch:
    def test_warms_catalog_cache(self, tmp_path, monkeypatch):
        fetched = []
        monkeypatch.setattr(rx.catalog, "load",
                            lambda sid, s, e: fetched.append(sid))
        misses = rx.prefetch_symbols(["AAPL", "MSFT"])
        assert fetched == ["yahoo:AAPL", "yahoo:MSFT"]
        assert misses == []

    def test_misses_recorded(self, tmp_path, monkeypatch):
        def boom(sid, s, e):
            raise ValueError(f"{sid}: not in catalog")
        monkeypatch.setattr(rx.catalog, "load", boom)
        misses = rx.prefetch_symbols(["ZZZ"])
        assert misses == ["ZZZ"]


class TestRunCopy:
    def test_copy_excludes_git(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        (repo / "s.py").write_text("print('hi')\n")
        (repo / ".git" / "HEAD").write_text("ref")
        dest = tmp_path / "runs" / "one"
        rx.make_run_copy(repo, dest)
        assert (dest / "s.py").exists()
        assert not (dest / ".git").exists()


class TestRunScript:
    def test_ok_run(self, tmp_path, monkeypatch):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("print('hello')\n")
        env = {"env": "main"}
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, env,
                         timeout=30, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "ok"
        assert row["env"] == "main"
        assert row["data_mode"] == "ours"
        assert row["runtime_s"] >= 0

    def test_error_run_records_stderr(self, tmp_path, monkeypatch):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("import sys\nsys.exit(2)\n")
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, {"env": "main"},
                         timeout=30, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "error"
        assert row["error"]

    def test_timeout_kills(self, tmp_path):
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("import time\ntime.sleep(60)\n")
        row = rx.execute(verdict(), tmp_path / "repo", run_copy, {"env": "main"},
                         timeout=2, data_mode="ours", results=tmp_path / "res")
        assert row["verdict"] == "timeout"

    def test_shim_env_forced_offline(self, tmp_path, monkeypatch):
        captured = {}
        real_popen = rx.subprocess.Popen

        def spy(cmd, **kw):
            captured["env"] = kw["env"]
            return real_popen(["true"], **kw)
        monkeypatch.setattr(rx.subprocess, "Popen", spy)
        monkeypatch.setattr(rx, "_python_for", lambda env: sys.executable)
        run_copy = tmp_path / "run"
        run_copy.mkdir()
        (run_copy / "s.py").write_text("pass\n")
        rx.execute(verdict(data_mode_hint="ours"), tmp_path / "repo", run_copy,
                   {"env": "main"}, timeout=10, data_mode="ours",
                   results=tmp_path / "res")
        py_path = captured["env"]["PYTHONPATH"]
        assert str(SHIM) in py_path
        assert captured["env"]["AUTOQUANT_DATA_ROOT"] == str(ROOT)
```

Note: `test_timeout_kills` sleeps 2s — acceptable.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_run_external.py -v -k "Prefetch or RunCopy or RunScript"`
Expected: FAIL — missing attributes

- [ ] **Step 3: Write the implementation** (append to `run_external.py`)

```python
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
    """Fresh copy of the repo minus .git — the original clone never mutates."""
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


def _child_env(data_mode: str) -> dict:
    env = os.environ.copy()
    if data_mode == "ours":
        # Shim first on the path: `import yfinance` resolves to the stub.
        env["PYTHONPATH"] = os.pathsep.join(
            [str(SHIM), env.get("PYTHONPATH", "")]).rstrip(os.pathsep)
        env["AUTOQUANT_DATA_ROOT"] = str(ROOT)
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


def execute(art: dict, repo_dir: Path, run_copy: Path, env: dict,
            timeout: int, data_mode: str, results: Path) -> dict:
    """Execute one artifact in the run-copy; return a leaderboard row."""
    target = run_copy / art["artifact"]
    started = time.monotonic()
    if art.get("kind") == "notebook":
        row = _run_notebook(art, target, env, timeout, data_mode, results)
    else:
        rc, _out, err = _launch([_python_for(env), str(target)],
                                cwd=run_copy, env=_child_env(data_mode),
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_run_external.py -v -k "Prefetch or RunCopy or RunScript"`
Expected: PASS (the notebook branch isn't exercised yet)

- [ ] **Step 5: Commit**

```bash
git add run_external.py tests/test_run_external.py
git commit -m "feat: run_external prefetch, run-copies, script execution (#27)"
```

### Task 12: Notebook execution + orchestration CLI

**Files:**
- Modify: `run_external.py`
- Modify: `tests/test_run_external.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
def write_nb(path: Path):
    nb = {"cells": [{"cell_type": "code", "execution_count": None,
                     "outputs": [], "source": ["print('ran')"],
                     "metadata": {}}],
          "metadata": {"kernelspec": {"name": "python3"}},
          "nbformat": 4, "nbformat_minor": 5}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(nb))


class TestRunNotebook:
    def test_executes_and_counts_cells(self, tmp_path):
        repo_dir = tmp_path / "repo"
        write_nb(repo_dir / "n.ipynb")
        run_copy = rx.make_run_copy(repo_dir, tmp_path / "run")
        row = rx.execute({"kind": "notebook", "artifact": "n.ipynb",
                          "repo": "o/r", "sha": "a" * 40},
                         repo_dir, run_copy, {"env": "main"},
                         timeout=120, data_mode="ours", results=tmp_path / "res")
        if row["verdict"] == "ok":  # main env has nbconvert/ipykernel via project deps
            assert row["cells_executed"] == 1
            executed = tmp_path / "res" / "o-r" / "n.ipynb"
            assert executed.exists()
            assert any(c.get("execution_count")
                       for c in json.loads(executed.read_text())["cells"])
        else:
            # env without notebook tooling: recorded, not crashed
            assert row["verdict"] in ("error", "timeout")


class TestMainWith:
    def test_full_flow_end_to_end(self, tmp_path, monkeypatch):
        repos = tmp_path / "repos" / "o-r"
        repos.mkdir(parents=True)
        (repos / "s.py").write_text("print('hello')\n")
        (repos / "manifest.json").write_text(json.dumps(
            {"repo": "o/r", "sha": "a" * 40, "notebooks": [], "scripts": [
                {"path": "s.py", "has_main": True, "n_lines": 1}],
             "spec_texts": [], "data_files": [], "deps": {}}))
        (tmp_path / "triage.jsonl").write_text(json.dumps(verdict()) + "\n")
        monkeypatch.setattr(rx, "REPOS", tmp_path / "repos")
        monkeypatch.setattr(rx, "TRIAGE", tmp_path / "triage.jsonl")
        monkeypatch.setattr(rx, "RESULTS", tmp_path / "res")
        monkeypatch.setattr(rx, "LEADERBOARD", tmp_path / "res" / "leaderboard.jsonl")
        monkeypatch.setattr(rx, "prefetch_symbols", lambda syms: [])

        assert rx.main_with(["--repo", "o/r"]) == 0
        rows = [json.loads(l) for l in
                (tmp_path / "res" / "leaderboard.jsonl").read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["verdict"] == "ok"

        # re-run skips
        monkeypatch.setattr(rx, "execute",
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError("re-ran")))
        assert rx.main_with(["--repo", "o/r"]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_run_external.py -v -k "TestRunNotebook or TestMainWith"`
Expected: FAIL

- [ ] **Step 3: Write the implementation** (append to `run_external.py`)

```python
def _run_notebook(art: dict, nb_path: Path, env: dict, timeout: int,
                  data_mode: str, results: Path) -> dict:
    """Execute via nbconvert in the artifact's env; save the executed
    notebook (inline outputs = browsable evidence) under results/."""
    cmd = [_python_for(env), "-m", "nbconvert", "--to", "notebook",
           "--execute", "--inplace",
           f"--ExecutePreprocessor.timeout={min(timeout, 120)}",
           str(nb_path)]
    rc, _out, err = _launch(cmd, cwd=nb_path.parent, env=_child_env(data_mode),
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
        "kind": art.get("kind"), "verdict": row["verdict"],
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

    print(f"\n{ok} ok, {failed} not-ok -> {LEADERBOARD.relative_to(ROOT)}")
    return 0


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
```

Note: the notebook test may take a few seconds (real nbconvert in the project env; the project declares nbconvert only if it is in pyproject — if absent, the test's else-branch covers it; do not force-install).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_run_external.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run_external.py tests/test_run_external.py
git commit -m "feat: run_external notebook execution + orchestration CLI (#27)"
```

### Task 13: Promotion into specs

**Files:**
- Modify: `run_external.py`
- Modify: `tests/test_run_external.py`

- [ ] **Step 1: Write the failing tests** (append)

```python
SPEC_YAML = """\
meta:
  slug: ext-o-r-demo
  title: "Demo strategy"
  url: null
  source: "github o/r"
  posted: null
  claim: "Demo claim."
data:
  universe: [SPY]
  bar: 1d
  fields: [open, high, low, close, volume]
  start: 2000-01-01
  end: null
  source: yfinance
  caveats: []
signal:
  definition: "raw = close > close.rolling(200).mean()"
  lookback_bars: 200
  lag_bars: 1
rules:
  entry: "raw is True"
  exit: "raw is False"
  direction: long_only
  position_when_flat: cash
  sizing: full_notional
  vol_target: null
  max_leverage: 1.0
  rebalance: on_signal_change
  execution_price: next_open
costs:
  commission_bps: 1.0
  slippage_bps: 5.0
  borrow_bps_annual: 0.0
  financing_bps_annual: 0.0
ambiguities: []
validation:
  oos_start: 2026-10-13
  is_oos_split: publication_date
  param_sweep: {}
  cost_sweep_bps: [0, 5, 10, 20, 50]
  null_tests: []
  min_trades: 30
  multiple_testing: {n_tested_so_far: null, method: deflated_sharpe}
verdict:
  status: PENDING
  reason: null
  report: null
"""


class TestPromote:
    def _setup(self, tmp_path, monkeypatch):
        specs = tmp_path / "specs"
        specs.mkdir()
        monkeypatch.setattr(rx, "SPECS", specs)
        triage_rows = [verdict("SPEC_ARTIFACT", artifact="idea.md")]
        triage_path = tmp_path / "triage.jsonl"
        triage_path.write_text("".join(json.dumps(r) + "\n" for r in triage_rows))
        monkeypatch.setattr(rx, "TRIAGE", triage_path)
        repo_dir = tmp_path / "repos" / "o-r"
        repo_dir.mkdir(parents=True)
        (repo_dir / "idea.md").write_text("# Buy above 200dma\nEntry: close > sma200. Exit below.")
        monkeypatch.setattr(rx, "REPOS", tmp_path / "repos")
        return repo_dir, specs

    def test_promote_writes_valid_spec(self, tmp_path, monkeypatch):
        import yaml
        repo_dir, specs = self._setup(tmp_path, monkeypatch)
        monkeypatch.setattr(rx.llm, "complete", lambda *a, **k: SPEC_YAML)
        out = rx.promote("o/r", "idea.md", model=None, extra=[])
        assert out.name == "ext-o-r-demo.yaml"
        spec = yaml.safe_load(out.read_text())
        assert rx.validate_spec(spec) == []
        assert spec["meta"]["slug"] == "ext-o-r-demo"

    def test_promote_rejects_wrong_slug_prefix(self, tmp_path, monkeypatch):
        repo_dir, specs = self._setup(tmp_path, monkeypatch)
        bad = SPEC_YAML.replace("  slug: ext-o-r-demo\n", "  slug: wrong-slug\n")
        monkeypatch.setattr(rx.llm, "complete", lambda *a, **k: bad)
        try:
            rx.promote("o/r", "idea.md", model=None, extra=[])
            raised = False
        except SystemExit:
            raised = True
        assert raised

    def test_validate_spec_required_keys(self):
        import yaml
        spec = yaml.safe_load(SPEC_YAML)
        assert rx.validate_spec(spec) == []
        no_costs = dict(spec)
        del no_costs["costs"]
        assert any("costs" in e for e in rx.validate_spec(no_costs))
        no_slug = {"meta": {}, "data": spec["data"], "signal": spec["signal"],
                   "rules": spec["rules"], "costs": spec["costs"],
                   "validation": spec["validation"]}
        assert any("slug" in e for e in rx.validate_spec(no_slug))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_run_external.py -v -k TestPromote`
Expected: FAIL — missing `promote`/`validate_spec`

- [ ] **Step 3: Write the implementation** (append to `run_external.py`; add `SPECS = ROOT / "specs"` next to the other constants)

```python
SPECS = ROOT / "specs"

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
    manifest = json.loads((repo_dir / "manifest.json").read_text())
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


def repo_slug_safe(repo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", repo.lower()).strip("-")


MAX_PROMPT_CHARS = 40_000


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
```

Note `repo_slug` (module-level, from harvest_repo naming) is not imported here — `repo_slug_safe` lives in run_external to keep the lane's modules independent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_run_external.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run_external.py tests/test_run_external.py
git commit -m "feat: run_external --promote into specs (#27)"
```

### Task 14: README + full-suite verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README** — add the external lane to the pipeline diagram and a usage section, matching the existing README's terse style:

```markdown
External lane (GitHub strategy repos — issues #22–#27):

    python3 harvest_repo.py LastAncientOne/Stock_Analysis_For_Quant   # clone + manifest
    python3 triage_repo.py --repo LastAncientOne/Stock_Analysis_For_Quant
    python3 run_external.py --repo LastAncientOne/Stock_Analysis_For_Quant
    python3 run_external.py --promote <repo>/<artifact>   # -> specs/ext-...yaml

Repo code never touches the project env (per-repo uv venvs) and never
touches the network (external_shim/ serves yfinance/pandas_datareader from
the local price cache).
```

Insert next to the existing pipeline stage list; keep the wording consistent with surrounding sections.

- [ ] **Step 2: Run the full suite**

Run: `uv run python -m pytest`
Expected: all PASS (288 existing + ~45 new)

- [ ] **Step 3: Smoke the CLIs offline-safe flags**

```bash
uv run python harvest_repo.py --help
uv run python triage_repo.py --help
uv run python run_external.py --help
uv run python -c "import repo_env"
```
Expected: usage text, no tracebacks.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: external strategy-repo lane usage in README (#22)"
```

---

## Post-plan: live pilot verification (manual, not in suite)

After merge, verify the acceptance criteria from the issues on the pilot repos:

```bash
uv run python harvest_repo.py Auquan/Tutorials rotmanfinhub/gamma-vega-rl-hedging LastAncientOne/Stock_Analysis_For_Quant
uv run python triage_repo.py --repo Auquan/Tutorials --limit 20   # calibrate first
uv run python run_external.py --repo Auquan/Tutorials --timeout 900
```

Check: manifest rows look sane, verdict distribution roughly matches issue #24's sanity expectations, leaderboard rows land in `results/external/leaderboard.jsonl`, executed notebooks appear under `results/external/<repo>/`.
