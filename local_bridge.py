#!/usr/bin/env python3
"""LOCAL BRIDGE — connects the dashboard's Chat tab to the local claude CLI.

The claude CLI does everything (model, auth via the user's subscription,
conversation memory via --resume); this server only formats and saves
transcripts under the repo's data/chat/. Runs on 127.0.0.1 by default —
not meant for public exposure.

    uv run python local_bridge.py [--port 8787]

Frontend: set VITE_CHAT_BRIDGE_URL (default http://127.0.0.1:8787).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import signal
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
DIGEST_PATH = ROOT / "frontend" / "src" / "content" / "snapshot.json"
CHAT_DIR = ROOT / "data" / "chat"
TIMEOUT_S = 300
TITLE_MAX = 60
SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
log = logging.getLogger("local_bridge")

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


async def run_claude(message: str, session_id: str | None) -> dict:
    """Spawn the claude CLI and parse its JSON output."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", *build_claude_args(message, session_id),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise CLIError("claude CLI not found on PATH") from exc
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), TIMEOUT_S)
    except asyncio.TimeoutError:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        raise CLIError(f"claude CLI timed out after {TIMEOUT_S}s") from None
    if proc.returncode != 0:
        raise CLIError((stderr or b"").decode(errors="ignore")[-300:]
                       or f"claude CLI exited {proc.returncode}")
    return parse_reply(stdout.decode(errors="ignore"))


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


class ChatBody(BaseModel):
    message: str
    sessionId: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _chat_path(session_id: str) -> Path:
    """Path for a transcript; ids are validated so they stay inside CHAT_DIR."""
    if not SESSION_ID.match(session_id or ""):
        raise ValueError(f"invalid session id: {session_id!r}")
    return CHAT_DIR / f"{session_id}.json"


def _title(question: str) -> str:
    return " ".join(question.split())[:TITLE_MAX]


def load_chat(session_id: str) -> dict | None:
    """A saved transcript, or None when it is missing or unreadable."""
    try:
        data = json.loads(_chat_path(session_id).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return None
    return data


def save_turn(session_id: str, role: str, text: str) -> None:
    """Append one turn to a transcript stored inside the repo workspace."""
    path = _chat_path(session_id)
    chat = load_chat(session_id) or {
        "sessionId": session_id, "title": "", "created": _now(),
        "messages": [],
    }
    chat["messages"].append({"role": role, "text": text, "at": _now()})
    if not chat.get("title") and role == "user":
        chat["title"] = _title(text)
    chat["updated"] = _now()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically so a crash cannot leave a half-written transcript
    with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, delete=False, suffix=".tmp") as tmp:
        json.dump(chat, tmp)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def list_chats() -> list[dict]:
    """Saved conversations, most recently active first."""
    if not CHAT_DIR.is_dir():
        return []
    chats = []
    for path in CHAT_DIR.glob("*.json"):
        chat = load_chat(path.stem)
        if chat is None:
            continue
        chats.append({
            "sessionId": chat.get("sessionId") or path.stem,
            "title": chat.get("title") or path.stem,
            "updated": chat.get("updated"),
            "messageCount": len(chat["messages"]),
        })
    chats.sort(key=lambda c: c.get("updated") or "", reverse=True)
    return chats


def record_turn(session_id: str | None, question: str, reply: str) -> None:
    """Save the exchange; a storage problem must never lose the reply."""
    if not session_id:
        return
    try:
        save_turn(session_id, "user", question)
        save_turn(session_id, "assistant", reply)
    except (OSError, ValueError) as exc:
        log.warning("could not save chat history: %s", exc)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/chats")
def chats() -> list[dict]:
    return list_chats()


@app.get("/api/chats/{session_id}")
def chat_transcript(session_id: str) -> dict:
    try:
        chat = load_chat(session_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if chat is None:
        raise HTTPException(404, "no such chat")
    return chat


@app.post("/api/chat")
async def chat(body: ChatBody) -> dict:
    if not body.message.strip():
        raise HTTPException(400, "message must not be empty")
    message = (seed_message(body.message, load_digest())
               if body.sessionId is None else body.message)
    try:
        out = await run_claude(message, body.sessionId)
    except CLIError as exc:
        raise HTTPException(502, str(exc)) from exc
    record_turn(out["sessionId"], body.message.strip(), out["reply"])
    return out


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
