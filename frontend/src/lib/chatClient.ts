/** Client for the local CLI bridge (local_bridge.py). The bridge shells out
 * to the claude CLI, keeps conversation memory via claude session ids, and
 * saves transcripts under the repo's data/chat/. */

const BRIDGE = import.meta.env.VITE_CHAT_BRIDGE_URL ?? "http://127.0.0.1:8787";

export type ChatOutcome =
  | { ok: true; reply: string; sessionId: string | null }
  | { ok: false; offline: boolean; error: string };

export interface ChatSummary {
  sessionId: string;
  title: string;
  updated: string | null;
  messageCount: number;
}

export interface ChatTurn {
  role: "user" | "assistant";
  text: string;
}

export async function sendChat(
  message: string,
  sessionId: string | null,
): Promise<ChatOutcome> {
  let res: Response;
  try {
    res = await fetch(`${BRIDGE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, sessionId }),
    });
  } catch {
    return {
      ok: false,
      offline: true,
      error:
        "The local bridge isn't reachable. Start it with: uv run python local_bridge.py",
    };
  }
  const body = (await res.json().catch(() => ({}))) as {
    reply?: string;
    sessionId?: string | null;
    error?: string;
  };
  if (!res.ok) {
    return {
      ok: false,
      offline: false,
      error: body.error ?? `bridge returned ${res.status}`,
    };
  }
  if (typeof body.reply !== "string") {
    return { ok: false, offline: false, error: "bridge returned no reply" };
  }
  return { ok: true, reply: body.reply, sessionId: body.sessionId ?? null };
}

/** Saved conversations from the workspace, newest first. Empty when the
 * bridge is unreachable or the payload is malformed. */
export async function listChats(): Promise<ChatSummary[]> {
  const body = await getJson("/api/chats");
  if (!Array.isArray(body)) return [];
  return body
    .filter((c): c is Record<string, unknown> =>
      !!c && typeof c === "object" && typeof c.sessionId === "string")
    .map((c) => ({
      sessionId: c.sessionId as string,
      title: typeof c.title === "string" && c.title ? c.title : "Untitled",
      updated: typeof c.updated === "string" ? c.updated : null,
      messageCount: typeof c.messageCount === "number" ? c.messageCount : 0,
    }));
}

/** One saved transcript's turns; empty when it is gone or malformed. */
export async function loadChat(sessionId: string): Promise<ChatTurn[]> {
  const body = await getJson(`/api/chats/${encodeURIComponent(sessionId)}`);
  const turns = (body as { messages?: unknown })?.messages;
  if (!Array.isArray(turns)) return [];
  return turns.filter(
    (t): t is ChatTurn =>
      !!t && typeof t === "object" &&
      (t.role === "user" || t.role === "assistant") &&
      typeof t.text === "string",
  );
}

async function getJson(path: string): Promise<unknown> {
  try {
    const res = await fetch(`${BRIDGE}${path}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}
