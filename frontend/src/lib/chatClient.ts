/** Client for the local CLI bridge (local_bridge.py). The bridge shells out
 * to the claude CLI and owns conversation memory via claude session ids. */

const BRIDGE = import.meta.env.VITE_CHAT_BRIDGE_URL ?? "http://127.0.0.1:8787";

export type ChatOutcome =
  | { ok: true; reply: string; sessionId: string | null }
  | { ok: false; offline: boolean; error: string };

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
