# Workspace Chat v2 — Local CLI Bridge — Design Spec

Date: 2026-10-29. Replaces the serverless/API design: the chat brain is the
local `claude` CLI (user's existing subscription, session resume built in).

## Verified CLI mechanics

- `claude -p MSG --output-format json` → `{result, session_id, ...}`
- `claude --resume SESSION_ID -p MSG --output-format json` → continues the
  conversation with full memory.

## Architecture

- `local_bridge.py` (repo root): FastAPI app, bound 127.0.0.1:8787 by default.
  - POST /api/chat {message, sessionId?} → {reply, sessionId}
    - no sessionId: seeds the conversation by prepending the research digest
      (counts, latest runs, failures, top specs — same data as the landing)
      to the first user message as grounding context.
    - runs `claude [--resume SID] -p MSG --output-format json` via async
      subprocess (300s timeout, process-group kill), parses result+session_id.
    - CORS: https://autoquant-blush.vercel.app + localhost dev origins.
    - 502 on CLI failure with the CLI's stderr tail; 504 on timeout.
  - GET /api/health → {ok: true, sessions: n}
- Frontend: Chat tab in workspace; `lib/chatClient.ts` posts to
  `VITE_CHAT_BRIDGE_URL` (default http://127.0.0.1:8787). Offline/unreachable →
  honest "start the local bridge" state with the exact command. sessionId held
  in React state (server stays stateless).
- Honest framing: assistant = the user's own Claude subscription via CLI;
  grounded in the digest on session start; nothing fabricated by our code.

## Not in scope

- Public exposure of the bridge (tunneling) — localhost/LAN use only for now.
- Multi-session history UI (single conversation per tab for now).
