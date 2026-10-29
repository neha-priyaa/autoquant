# Workspace Chat (LLM) — Design Spec

Date: 2026-10-29. Adds a real-LLM chat to the workspace dashboard.

## Decisions

- Brain: Vercel serverless function (`frontend/api/chat.ts`, Node runtime) calling
  the **Anthropic Messages API** via the official `@anthropic-ai/sdk`, model
  **claude-opus-5-5**. Key from `ANTHROPIC_API_KEY` (Vercel env var — user-provided).
- Grounding: a compact **research digest** (counts, latest 5 runs, current failures,
  top 3 specs by |Sharpe|, catalog count, snapshot timestamp) built at build time
  from the workspace snapshot (`src/content/chatContext.ts`), embedded in the
  system prompt with hard anti-fabrication rules: answer only from the digest,
  say "not in the snapshot" otherwise.
- Honest failure: 503 + setup message when the key is absent; typed SDK errors
  surfaced as readable messages (auth → "check ANTHROPIC_API_KEY", rate limit,
  API errors).
- UI: Chat tab in the workspace sidebar — bubbles, Enter-to-send input, typing
  indicator, auto-scroll, last-8-messages history sent per turn, disabled send
  while waiting. Theme/skin aware via tokens.

## Contracts

- POST /api/chat  body: {messages: [{role: "user"|"assistant", content: string}]}
  → 200 {reply: string} | 400 (bad body) | 405 (method) | 429 (rate limit, 10
  msg/min/IP) | 503 {error, setup: true} (no key) | 502 (upstream error)
- Constraints: ≤12 messages, ≤4000 chars/message, non-streaming, max_tokens 16000.

## Vercel deploy change

`frontend/vercel.json` (project root) sets framework=vite + SPA rewrites
(replacing public/vercel.json); `api/chat.ts` auto-bundles as a serverless
function. Deploy command becomes `npx vercel deploy --prod --yes` from
`frontend/` (Vercel runs the build). Public URL unchanged.

## Tests

Vitest with a mocked SDK: body validation, history capping, reply extraction,
503-without-key, typed-error mapping. UI test: send/receive with mocked
fetch-client, unconfigured note. Digest unit test. Gates: vitest, build,
Python suite.
