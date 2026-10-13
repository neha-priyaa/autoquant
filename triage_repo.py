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
    if not isinstance(result, dict):
        return {**key, "error": "unparseable reply: not a JSON object"}
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
    try:
        shown = TRIAGE.relative_to(ROOT)
    except ValueError:  # TRIAGE redirected outside the repo (tests)
        shown = TRIAGE
    print(f"verdicts -> {shown}")
    return 0


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
