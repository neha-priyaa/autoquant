#!/usr/bin/env python3
"""LOCAL BRIDGE — connects the dashboard's Chat tab to the local claude CLI.

The claude CLI does everything (model, auth via the user's subscription,
conversation memory via --resume); this server only formats. Runs on
127.0.0.1 by default — not meant for public exposure.

    uv run python local_bridge.py [--port 8787]

Frontend: set VITE_CHAT_BRIDGE_URL (default http://127.0.0.1:8787).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import signal
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DIGEST_PATH = ROOT / "frontend" / "src" / "content" / "snapshot.json"
TIMEOUT_S = 300

app = FastAPI(title="autoquant local bridge")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://autoquant-blush.vercel.app"],
    # any local dev port (5173, 4173, 4199, …); non-local origins stay blocked
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class CLIError(Exception):
    """The claude CLI failed (nonzero exit / is_error / unparseable output)."""


def build_claude_args(message: str, session_id: str | None) -> list[str]:
    """claude CLI argv: --resume continues a session's full memory."""
    args = []
    if session_id:
        args += ["--resume", session_id]
    args += ["-p", message, "--output-format", "json"]
    return args


def parse_reply(stdout: str) -> dict:
    """Extract {reply, sessionId} from the CLI's JSON output."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CLIError(f"unparseable CLI output: {exc}") from exc
    if data.get("is_error"):
        raise CLIError(str(data.get("result") or "CLI reported an error"))
    reply = data.get("result")
    if not isinstance(reply, str) or not reply.strip():
        raise CLIError("CLI returned an empty reply")
    return {"reply": reply, "sessionId": data.get("session_id")}


def seed_message(message: str, digest: str) -> str:
    """First turn of a session: ground the assistant in the research digest."""
    return (
        "You are AutoQuant's research assistant. Answer only from the "
        "research snapshot below — if something is not in it, say so; "
        "never invent results, metrics, or citations.\n\n"
        f"--- RESEARCH SNAPSHOT ---\n{digest}\n--- END SNAPSHOT ---\n\n"
        f"{message}"
    )


def load_digest() -> str:
    """Compact research digest from the build-time snapshot."""
    snapshot = json.loads(DIGEST_PATH.read_text())
    counts = snapshot.get("counts", {})
    w = snapshot.get("workspace", {})
    runs = sorted(w.get("runs", []), key=lambda r: r.get("date") or "",
                  reverse=True)
    latest = "; ".join(
        f"{r.get('slug')} [{r.get('status')} sharpe={r.get('netSharpe')}]"
        for r in runs[:5])
    failed = "; ".join(f["slug"] for f in w.get("failed", [])[:5]) or "none"
    specs = "; ".join(s.get("slug", "") for s in w.get("specs", [])[:8])
    return (
        f"Generated {snapshot.get('generatedAt')}. "
        f"Counts: {counts}. "
        f"Latest runs: {latest}. "
        f"Currently failing codegen: {failed}. "
        f"Specs include: {specs}. "
        f"Catalog: {w.get('catalogCount', 0)} data series."
    )


async def run_claude(message: str, session_id: str | None) -> dict:
    """Spawn the claude CLI and parse its JSON output."""
    proc = await asyncio.create_subprocess_exec(
        "claude", *build_claude_args(message, session_id),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), TIMEOUT_S)
    except asyncio.TimeoutError:
        try:
            import os
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        raise CLIError(f"claude CLI timed out after {TIMEOUT_S}s")
    if proc.returncode != 0:
        raise CLIError((stderr or b"").decode(errors="ignore")[-300:]
                       or f"claude CLI exited {proc.returncode}")
    return parse_reply(stdout.decode(errors="ignore"))


class ChatBody(BaseModel):
    message: str
    sessionId: str | None = None


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/chat")
async def chat(body: ChatBody) -> dict:
    if not body.message.strip():
        raise HTTPException(400, "message must not be empty")
    message = (seed_message(body.message, load_digest())
               if body.sessionId is None else body.message)
    try:
        return await run_claude(message, body.sessionId)
    except CLIError as exc:
        raise HTTPException(502, str(exc)) from exc


def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--host", default="127.0.0.1")
    args = ap.parse_args(argv)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_with())
