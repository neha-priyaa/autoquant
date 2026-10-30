import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send } from "lucide-react";
import { sendChat } from "../../lib/chatClient";

interface Msg { role: "user" | "assistant"; text: string }

export default function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: "smooth" });
  }, [messages, waiting]);

  async function submit() {
    const text = input.trim();
    if (!text || waiting) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setWaiting(true);
    const out = await sendChat(text, sessionId);
    setWaiting(false);
    if (out.ok) {
      setSessionId(out.sessionId);
      setMessages((m) => [...m, { role: "assistant", text: out.reply }]);
    } else {
      setMessages((m) => [...m, {
        role: "assistant",
        text: out.offline
          ? `⚠ ${out.error}`
          : `⚠ The bridge failed: ${out.error}`,
      }]);
    }
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <h1 className="text-4xl font-light">Chat</h1>
      <p className="mt-2 font-mono text-xs text-dim">
        YOUR LOCAL CLAUDE SUBSCRIPTION VIA THE CLI BRIDGE — answers are grounded
        in the research snapshot at session start
      </p>

      <div className="mt-6 flex min-h-0 flex-1 flex-col overflow-y-auto border border-line bg-surface/30 p-4">
        {messages.length === 0 ? (
          <div className="m-auto max-w-md text-center text-sm text-dim">
            Ask about your research: counts, runs, failures, specs, catalog…
            <div className="mt-3 font-mono text-[11px]">
              requires the local bridge:{" "}
              <code className="text-ink">uv run python local_bridge.py</code>
            </div>
          </div>
        ) : (
          messages.map((m, i) =>
            m.role === "assistant" ? (
              <div key={i}
                   className="md my-2 max-w-[85%] self-start border border-line bg-bg px-4 py-3 text-sm leading-relaxed text-ink/95">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              </div>
            ) : (
              <div key={i}
                   className="my-2 max-w-[80%] self-end border border-accent/40 bg-accent/15 px-4 py-2.5 text-sm leading-relaxed">
                {m.text}
              </div>
            ),
          )
        )}
        {waiting && (
          <div className="my-2 self-start border border-line bg-bg px-4 py-2.5 font-mono text-xs text-dim">
            thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        className="mt-4 flex gap-3"
        onSubmit={(e) => { e.preventDefault(); void submit(); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={waiting ? "waiting for the reply…" : "Ask about your research…"}
          aria-label="Message"
          className="flex-1 border border-line bg-bg px-4 py-3 font-mono text-sm text-ink placeholder:text-dim/60"
        />
        <button
          type="submit"
          disabled={waiting || !input.trim()}
          aria-label="Send message"
          className="flex items-center gap-2 bg-accent px-5 py-3 font-mono text-xs font-medium tracking-widest text-bg transition-opacity disabled:opacity-40"
        >
          <Send className="h-3.5 w-3.5" /> SEND
        </button>
      </form>
    </div>
  );
}
