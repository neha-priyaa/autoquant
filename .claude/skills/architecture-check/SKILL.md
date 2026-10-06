---
name: architecture-check
description: Audit this repo against its documented architecture (README, AGENTS.md, docs/superpowers/) and report conformance drift with file:line evidence. Use when the user asks to check repo conformance, audit the architecture, find docs/code drift, or verify the pipeline matches its documentation.
tools: Read, Grep, Glob, Bash
---

# Architecture Conformance Audit

You are auditing this repository against its documented architecture.
**Read-only by design**: you report drift, you never fix it. Every finding
cites `file:line` evidence. Every verdict is pass / warn / fail.

## Procedure

### Step 1 — Read the sources of truth

Read these first. All checks below derive from what they actually say —
do NOT substitute this skill's examples for the documents if they disagree.
The documents always win.

1. `README.md` — the Stages table, the artifact-contract prose
   ("independent and resumable", what is committed vs ignored), the LLM
   adapter section, the article-sources section, the data-catalog section.
2. `AGENTS.md` — working guidelines.
3. `ls docs/superpowers/plans/ docs/superpowers/specs/` — feature history.

### Step 2 — Pipeline vs README

- Extract the documented stage table from the README. For each listed
  entry point, confirm the script exists and runs: `python3 <script> --help`
  (exit 0). Record any documented stage whose script is missing or broken.
- Reverse direction: `git ls-files '*.py'` (plus an `ls` for untracked
  scripts) — flag any script that looks pipeline-participating (reads or
  writes `data/articles.jsonl`, `data/pages/`, `data/triage.jsonl`,
  `specs/`, `strategies/`, or `results/`) but is absent from the README's
  stage table.
- Artifact contracts:
  - All harvesters append to the same `data/articles.jsonl` using
    `harvest.entry_row()` (grep for `entry_row` imports). Flag a harvester
    that hand-rolls its own row dict.
  - Slug prefixes: `cboe-` and `arxiv-` (grep `row["slug"] =`).
  - Stage outputs land where the README says: `data/pages/`,
    `data/triage.jsonl`, `specs/<slug>.yaml`, `strategies/<slug>.py`,
    `results/leaderboard.jsonl` (grep the `Path` constants at each
    script's top).
  - Resumability: each stage has skip-existing logic (e.g. `pending_specs`
    in codegen.py, the cached-page short-circuit in fetch.py, url-dedupe
    in the harvesters). Flag a stage that would redo completed work.

### Step 3 — LLM adapter exclusivity

- The three LLM stages (triage.py, extract.py, codegen.py) must reach the
  LLM CLI only through `llm.py`: `grep -n "subprocess\|os.system\|Popen"
  triage.py extract.py codegen.py` — any hit outside llm.py is a fail.
- Compare the README's LLM section against `llm.py` reality: env vars
  (`AUTOQUANT_LLM_CMD`, `AUTOQUANT_LLM_EXTRA_ARGS`), `{model}` placeholder
  behavior, `--llm-arg`, preflight, and the circuit breaker (k=3, CLI-level
  errors only) are all still described accurately.
- If the README documents compare mode (`--compare-models` / `--pick`),
  confirm those flags exist in codegen.py and artifacts go to
  `strategies/compare/<label>/` without polluting `pending_specs`.

### Step 4 — Git hygiene

- README claims specs, strategy code, and `results/leaderboard.jsonl` are
  committed while page caches, price caches, and full reports stay out.
  Verify: `.gitignore` covers `data/pages/`, `data/catalog/` (or the
  documented cache paths) and does NOT cover `specs/`, `strategies/`,
  `results/leaderboard.jsonl`. Use `git check-ignore -v <path>` and
  `git ls-files` for evidence.

### Step 5 — AGENTS.md spot-checks

- `grep -rn "type: ignore" --include="*.py" .` — any hit is a fail.
- `find . -name "*.py" -perm -111 -not -path "./.git/*"` — executable-bit
  Python files are a fail (daemons/executables are against guidelines).
- TOML reading uses stdlib `tomllib` (grep `tomllib|toml.load|pytoml`).
- Tests parallel to source layout: a module `<root>.py` has its tests at
  `tests/test_<root>.py` (flat layout, so `tests/test_<module>.py`).

### Step 6 — Docs ↔ reality

- Every `docs/superpowers/plans/*.md` and `specs/*.md` describes a feature
  that exists: spot-check that files/flags/functions the docs name are
  present (`Glob`/`Grep`). Flag docs describing abandoned features and
  shipped features missing their plan doc (warn, not fail).
- Re-read AGENTS.md's "Running the project" section: its tooling claims
  (dependency declaration, test runner) must match `pyproject.toml` /
  actual test setup. This section has drifted before.

### Step 7 — Report

Produce a markdown report in exactly this shape, suitable for pasting into
an issue or PR description:

```
# Architecture conformance report (<date>)

| Section | Verdict | Findings |
|---|---|---|
| Pipeline vs README | pass/warn/fail | <one line per finding with file:line> |
| LLM adapter | ... | ... |
| Git hygiene | ... | ... |
| AGENTS.md spot-checks | ... | ... |
| Docs ↔ reality | ... | ... |

## Drift summary
<bulleted list of every warn/fail, most severe first, each with the doc
claim vs the observed reality and file:line on both sides>
```

Verdict rules: fail = documented behavior is violated by code (or vice
versa); warn = cosmetic drift, stale doc, or a gap that is merely risky;
pass = evidence checked, nothing found. An empty section with evidence
cited is a pass — say what you checked, not just what you found.
