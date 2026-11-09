import { useState } from "react";
import { Check, Copy } from "lucide-react";

/** Runnable terminal command shown in empty states, one-click copyable. */
export default function CliSnippet({ command, label }: { command: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="mx-auto max-w-xl text-center">
      {label && <p className="text-sm text-dim">{label}</p>}
      <div className="mt-3 flex items-center justify-between gap-3 border border-line bg-bg px-4 py-2.5">
        <code className="min-w-0 overflow-x-auto whitespace-nowrap font-mono text-xs text-ink">
          {command}
        </code>
        <button
          aria-label={`Copy command: ${command}`}
          onClick={() => {
            navigator.clipboard?.writeText(command).then(() => {
              setDone(true);
              setTimeout(() => setDone(false), 1500);
            });
          }}
          className="shrink-0 text-dim transition-colors hover:text-accent"
        >
          {done ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
    </div>
  );
}
