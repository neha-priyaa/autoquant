# Issue #12: multi-LLM comparison for codegen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optional `--compare-models` mode for codegen that runs each prompt once per configured LLM CLI, writes per-label artifacts under `strategies/compare/<label>/`, prints a comparison table, and offers `--pick` to promote a winner.

**Architecture:** `llm.py` learns to address N named templates (`parse_compare`, `_build_argv_from`, `complete(template=...)`); `codegen.py` fans out per candidate reusing the existing `publish` machinery with a per-label directory. Off by default.

**Tech Stack:** Python 3 stdlib (argparse, shlex, hashlib), pytest. Branch: `issue12-compare-models`.

---

### Task 1: `llm.parse_compare` + template-parameterized argv

**Files:**
- Modify: `llm.py`
- Test: `tests/test_llm.py` (new class `TestParseCompare`, `TestBuildArgvFrom`)

- [ ] **Step 1: Write failing tests** (append to `tests/test_llm.py`)

```python
class TestParseCompare:
    def test_label_cmd_pairs(self):
        assert llm.parse_compare("sonnet=claude -p --model X, opus=claude -p --model Y") == [
            ("sonnet", "claude -p --model X"), ("opus", "claude -p --model Y")]

    def test_missing_label_falls_back_to_model_flag(self):
        assert llm.parse_compare("claude -p --model sonnet-4-6") == [
            ("sonnet-4-6", "claude -p --model sonnet-4-6")]

    def test_missing_label_no_model_flag_hashes_cmd(self):
        pairs = llm.parse_compare("opencode run")
        (label, cmd) = pairs[0]
        assert cmd == "opencode run"
        assert len(label) == 6

    def test_empty_entry_raises(self):
        with pytest.raises(llm.LLMError, match="expected 'label=cmd'"):
            llm.parse_compare("just-a-cmd-no-equals, a=b")

    def test_duplicate_label_raises(self):
        with pytest.raises(llm.LLMError, match="duplicate"):
            llm.parse_compare("a=cmd1,a=cmd2")

    def test_empty_spec_raises(self):
        with pytest.raises(llm.LLMError, match="no compare"):
            llm.parse_compare("  ,  ")


class TestBuildArgvFrom:
    def test_template_placeholder(self):
        argv = llm._build_argv_from("crush run -q {model}", "m1", None)
        assert argv == ["crush", "run", "-q", "m1"]

    def test_template_appends_model_flag(self):
        argv = llm._build_argv_from("claude -p", "m1", None)
        assert argv == ["claude", "-p", "--model", "m1"]


class TestPreflightCompare:
    def test_preflight_covers_compare_candidates(self, monkeypatch):
        monkeypatch.setenv("AUTOQUANT_LLM_CMD", "opencode run")
        monkeypatch.setenv("AUTOQUANT_LLM_COMPARE", "x=definitely-not-a-real-cli-xyz run")
        with pytest.raises(llm.LLMError, match="definitely-not-a-real-cli-xyz"):
            llm.preflight()

    def test_preflight_ok_when_compare_unset(self, monkeypatch):
        monkeypatch.setenv("AUTOQUANT_LLM_CMD", "python3")
        monkeypatch.delenv("AUTOQUANT_LLM_COMPARE", raising=False)
        llm.preflight()
```

- [ ] **Step 2: Run, verify FAIL** — `python3 -m pytest tests/test_llm.py::TestParseCompare -v`

- [ ] **Step 3: Implement in `llm.py`**

```python
import hashlib  # add to imports

def _build_argv_from(template: str, model: str | None = None,
                     extra: list[str] | None = None) -> list[str]:
    if "{model}" in template:
        argv = shlex.split(template.format(model=model or ""))
    else:
        argv = shlex.split(template)
        if model:
            argv += ["--model", model]
    argv += list(extra or [])
    argv += shlex.split(os.environ.get("AUTOQUANT_LLM_EXTRA_ARGS", ""))
    return argv


def build_argv(model=None, extra=None):
    return _build_argv_from(os.environ.get("AUTOQUANT_LLM_CMD", DEFAULT_CMD), model, extra)


def preflight_for(template: str) -> None:
    argv = shlex.split(template)
    if shutil.which(argv[0]) is None:
        raise LLMError(f"`{argv[0]}` CLI not found on PATH ({template!r})")


def parse_compare(spec: str) -> list[tuple[str, str]]:
    """'label=cmd,label=cmd' -> [(label, template), ...]. Label falls back to
    the last --model value, else a hash of the command."""
    pairs, seen = [], set()
    for raw in spec.split(","):
        raw = raw.strip()
        if not raw:
            continue
        label, sep, cmd = raw.partition("=")
        label, cmd = label.strip(), cmd.strip()
        if not sep or not cmd:
            raise LLMError(f"invalid compare entry {raw!r}: expected 'label=cmd'")
        if not label:
            models = re.findall(r"--model\s+(\S+)", cmd)
            label = models[-1] if models else hashlib.sha256(cmd.encode()).hexdigest()[:6]
        if label in seen:
            raise LLMError(f"duplicate compare label {label!r}")
        seen.add(label)
        pairs.append((label, cmd))
    if not pairs:
        raise LLMError("no compare entries in compare spec")
    return pairs


def preflight() -> None:
    preflight_for(os.environ.get("AUTOQUANT_LLM_CMD", DEFAULT_CMD))
    cmp_spec = os.environ.get("AUTOQUANT_LLM_COMPARE", "")
    if cmp_spec:
        for _label, cmd in parse_compare(cmp_spec):
            preflight_for(cmd)
```

Also update `complete()` to accept `template: str | None = None` and use
`_build_argv_from(template, ...)` when given, else `build_argv(...)`. Existing
`build_argv` behavior/tests unchanged.

- [ ] **Step 4: Run full llm tests** — `python3 -m pytest tests/test_llm.py -v` → PASS
- [ ] **Step 5: Commit** — `git add -A && git commit -m "llm: named compare configs (parse_compare, template-parameterized argv)"`

### Task 2: codegen compare fan-out + per-label artifacts + summary

**Files:**
- Modify: `codegen.py`
- Test: `tests/test_codegen_compare.py` (new)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_codegen_compare.py
"""Tests for codegen --compare-models fan-out and --pick promotion."""
from __future__ import annotations

import codegen
import llm
import pytest
import yaml

VALID_MODULE = (
    "import pandas as pd\n"
    "def signal(df, **params):\n"
    "    return (df.close > df.close.rolling(5).mean()).astype(float)\n"
)


def setup_specs(tmp_path, n=1):
    specs = tmp_path / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        (specs / f"s{i}.yaml").write_text(
            f"meta:\n  slug: s{i}\nsignal:\n  definition: d\n  lag_bars: 1\n")
    return specs


def wire(tmp_path, monkeypatch, complete):
    monkeypatch.setattr(codegen, "ROOT", tmp_path)
    monkeypatch.setattr(codegen, "SPECS", tmp_path / "specs")
    monkeypatch.setattr(codegen, "STRATEGIES", tmp_path / "strategies")
    monkeypatch.setattr(codegen.llm, "preflight", lambda: None)
    monkeypatch.setattr(codegen.llm, "complete", complete)


class TestCompareFanout:
    def test_each_label_gets_its_own_artifact(self, tmp_path, monkeypatch):
        calls = []

        def fake_complete(prompt, **k):
            calls.append(k.get("template"))
            return VALID_MODULE

        wire(tmp_path, monkeypatch, fake_complete)
        rc = codegen.main_with(["--jobs", "1", "--limit", "1",
                                "--compare-models", "a=cmd-a,b=cmd-b"])
        assert rc == 0
        strategies = tmp_path / "strategies"
        assert (strategies / "compare" / "a" / "s0.py").exists()
        assert (strategies / "compare" / "b" / "s0.py").exists()
        assert not (strategies / "s0.py").exists()  # never published to trusted name
        assert sorted(calls) == ["cmd-a", "cmd-b"]

    def test_compare_subdir_invisible_to_pending_specs(self, tmp_path):
        specs = setup_specs(tmp_path)
        strategies = tmp_path / "strategies"
        (strategies / "compare" / "a").mkdir(parents=True)
        (strategies / "compare" / "a" / "s0.py").write_text("x = 1\n")
        assert [p.stem for p in codegen.pending_specs(specs, strategies, False)] == ["s0"]

    def test_smoke_fail_writes_per_label_error(self, tmp_path, monkeypatch):
        wire(tmp_path, monkeypatch, lambda prompt, **k: "x = 1\n")
        rc = codegen.main_with(["--jobs", "1", "--limit", "1",
                                "--compare-models", "a=cmd-a"])
        assert rc == 0  # comparison never aborts the batch on stage-level errors
        assert (tmp_path / "strategies" / "compare" / "a" / "s0.error").exists()

    def test_summary_table_printed(self, tmp_path, monkeypatch, capsys):
        wire(tmp_path, monkeypatch, lambda prompt, **k: VALID_MODULE)
        codegen.main_with(["--jobs", "1", "--limit", "1",
                           "--compare-models", "a=cmd-a"])
        out = capsys.readouterr().out
        assert "label" in out and "a" in out and "coded" in out
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement in `codegen.py`**

- `generate_one(spec_path, model, extra=None, template=None)` — pass `template`
  through to `llm.complete(prompt, model=model, extra=extra, timeout=CLI_TIMEOUT,
  template=template)`.
- New CLI flags: `--compare-models` (default None; env fallback
  `AUTOQUANT_LLM_COMPARE`), `--pick`, `--slug` (for pick).
- New module-level `COMPARE = ROOT / "strategies" / "compare"`.
- In `main_with`, when compare is set:
  - `candidates = llm.parse_compare(compare_spec)`; raise/exit on `LLMError`.
  - For each pending spec, run `generate_one(..., template=cmd)` per candidate
    and `publish(result, spec, COMPARE / label)`. Track wall time with
    `time.monotonic()` around generate+publish.
  - Per-label result list; call `llm.circuit_break(per_label_done)` per label —
    an aborted label stops receiving new specs, others continue.
  - Summary table printed at end:
    `label  coded  smoke_failed  cli_failed  median_s`.
- Jobs/executor: reuse the existing ThreadPoolExecutor; futures tagged
  `(spec_path, label)`.

- [ ] **Step 4: Run** — `python3 -m pytest tests/test_codegen_compare.py tests/test_codegen.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -am "codegen: --compare-models fan-out with per-label artifact namespaces"`

### Task 3: `--pick` promotion

**Files:**
- Modify: `codegen.py`
- Test: `tests/test_codegen_compare.py`

- [ ] **Step 1: Failing tests**

```python
class TestPick:
    def test_promotes_passed_candidate(self, tmp_path, monkeypatch, capsys):
        strategies = tmp_path / "strategies"
        cand = strategies / "compare" / "a"
        cand.mkdir(parents=True)
        (cand / "s0.py").write_text(VALID_MODULE)
        wire(tmp_path, monkeypatch, lambda prompt, **k: VALID_MODULE)
        rc = codegen.main_with(["--pick", "a", "--slug", "s0"])
        assert rc == 0
        assert (strategies / "s0.py").read_text() == VALID_MODULE
        assert (strategies / "compare" / "a" / "s0.py").exists()  # original kept

    def test_refuses_missing_candidate(self, tmp_path, monkeypatch):
        wire(tmp_path, monkeypatch, lambda prompt, **k: VALID_MODULE)
        with pytest.raises(SystemExit, match="no candidate"):
            codegen.main_with(["--pick", "zzz", "--slug", "s0"])

    def test_refuses_failed_candidate(self, tmp_path, monkeypatch):
        strategies = tmp_path / "strategies"
        cand = strategies / "compare" / "a"
        cand.mkdir(parents=True)
        (cand / "s0.error").write_text('{"error": "boom"}\n')
        wire(tmp_path, monkeypatch, lambda prompt, **k: VALID_MODULE)
        with pytest.raises(SystemExit, match="failed"):
            codegen.main_with(["--pick", "a", "--slug", "s0"])

    def test_pick_clears_stale_error_marker(self, tmp_path, monkeypatch):
        strategies = tmp_path / "strategies"
        cand = strategies / "compare" / "a"
        cand.mkdir(parents=True)
        (cand / "s0.py").write_text(VALID_MODULE)
        (strategies / "s0.error").write_text('{"error": "old"}\n')
        wire(tmp_path, monkeypatch, lambda prompt, **k: VALID_MODULE)
        codegen.main_with(["--pick", "a", "--slug", "s0"])
        assert not (strategies / "s0.error").exists()
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
def pick(label: str, slug: str) -> None:
    cand_dir = COMPARE / label
    src = cand_dir / f"{slug}.py"
    if not src.exists():
        sys.exit(f"error: no candidate {src.relative_to(ROOT)}")
    if (cand_dir / f"{slug}.error").exists():
        sys.exit(f"error: candidate {label}/{slug} failed its smoke test")
    dest = STRATEGIES / f"{slug}.py"
    tmp = dest.with_suffix(".py.tmp")
    tmp.write_text(src.read_text())
    tmp.replace(dest)
    (STRATEGIES / f"{slug}.error").unlink(missing_ok=True)
    print(f"picked {label}/{slug} -> strategies/{slug}.py")
```

In `main_with`, handle `--pick` before anything else (with `--slug` required).

- [ ] **Step 4: Run full suite** — `python3 -m pytest tests/ -v` → PASS
- [ ] **Step 5: Commit** — `git commit -am "codegen: --pick promotes a compare candidate to strategies/<slug>.py"`

### Task 4: README + circuit-breaker-per-label test

**Files:**
- Modify: `README.md`
- Test: `tests/test_codegen_compare.py`

- [ ] **Step 1: Failing test** — one label CLI-fails 3x, the other succeeds; assert aborted label has exactly 3 `.error` markers, other label's artifacts exist, rc == 1 with "aborting" in stdout.

- [ ] **Step 2-3: Run / fix if needed**
- [ ] **Step 4: README** — add under the LLM env-var docs:

```markdown
### Model comparison (optional)

`python3 codegen.py --compare-models "sonnet=claude -p --model sonnet-4-6,opus=claude -p --model opus-4-6"`

Each pending spec is generated once per candidate; artifacts land in
`strategies/compare/<label>/` with a per-label pass/fail + timing table.
Pick a winner with `python3 codegen.py --pick sonnet --slug <slug>`.
Selection is manual; nothing is auto-promoted. (Env fallback:
`AUTOQUANT_LLM_COMPARE`.)
```

- [ ] **Step 5: Full suite + commit** — `python3 -m pytest tests/ -q && git commit -am "codegen: per-label circuit breaker; README compare docs"`
