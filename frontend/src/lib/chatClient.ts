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
        "The local bridge isn't reachable. Start it with: uv run python local_bridge.py. " +
        "If it is running, your browser may be blocking access to the local network — " +
        "allow the connection when prompted (Chrome asks on first use).",
    };
  }
  const body = (await res.json().catch(() => ({}))) as {
    reply?: string;
    sessionId?: string | null;
    detail?: unknown;
  };
  if (!res.ok) {
    return {
      ok: false,
      offline: false,
      error: errorDetail(body.detail) ?? `bridge returned ${res.status}`,
    };
  }
  if (typeof body.reply !== "string") {
    return { ok: false, offline: false, error: "bridge returned no reply" };
  }
  return { ok: true, reply: body.reply, sessionId: body.sessionId ?? null };
}

/** Saved conversations from the workspace, newest first. null when the
 * bridge can't be reached (history availability unknown); [] only when the
 * bridge answered with none or a malformed payload. */
export async function listChats(): Promise<ChatSummary[] | null> {
  const body = await getJson("/api/chats");
  if (body === null) return null;
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

/** One saved transcript's turns. null when the bridge can't be reached or
 * the chat is gone; [] only when it answered with none or a malformed
 * payload. */
export async function loadChat(sessionId: string): Promise<ChatTurn[] | null> {
  const body = await getJson(`/api/chats/${encodeURIComponent(sessionId)}`);
  if (body === null) return null;
  const turns = (body as { messages?: unknown })?.messages;
  if (!Array.isArray(turns)) return [];
  return turns.filter(
    (t): t is ChatTurn =>
      !!t && typeof t === "object" &&
      (t.role === "user" || t.role === "assistant") &&
      typeof t.text === "string",
  );
}

/** FastAPI reports failures as `detail`: a string for HTTPException and an
 * array of field errors for a malformed body. */
function errorDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (!Array.isArray(detail)) return null;
  const messages = detail
    .map((entry) =>
      entry && typeof entry === "object" &&
      typeof (entry as { msg?: unknown }).msg === "string"
        ? (entry as { msg: string }).msg
        : null)
    .filter((msg): msg is string => !!msg);
  return messages.length > 0 ? messages.join("; ") : null;
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
