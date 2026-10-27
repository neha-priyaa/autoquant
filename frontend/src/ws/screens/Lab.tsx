import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check } from "lucide-react";
import { StatusDot } from "../../components/StatusDot";
import { workspace } from "../../content/workspace";

function CopyButton({ text, label }: { text: string; label: string }) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function copy(): Promise<void> {
    setError(null);
    setDone(false);
    if (!navigator.clipboard?.writeText) {
      setError("Clipboard is unavailable here. Open the YAML preview to copy it manually.");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1500);
    } catch {
      setError("Could not copy. Allow clipboard access or copy from the YAML preview.");
    }
  }
  return (
    <>
      <button
        onClick={copy}
        aria-label={`Copy ${label}`}
        className="inline-flex items-center gap-1 font-mono text-[11px] text-dim hover:text-accent"
      >
        {done ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
        <span role="status">{done ? "copied" : "copy"}</span>
      </button>
      {error && <p role="alert" className="font-mono text-xs text-dim">{error}</p>}
    </>
  );
}

export function SpecDetail({ slug }: { slug: string }) {
  const spec = workspace.specs.find((s) => s.slug === slug);
  const code = spec?.hasCode
    ? "(generated code available in strategies/ — snapshot carries specs only)"
    : null;
  if (!spec) return <p className="mt-10 text-dim">Spec not found: {slug}</p>;
  // Older snapshots used an ellipsis as the truncation marker.
  const rawTruncated = spec.rawTruncated ?? spec.raw.trimEnd().endsWith("…");
  const run = workspace.runs.find((r) => r.slug === slug && r.lane === "article");
  return (
    <div>
      <div className="flex items-center gap-3">
        <StatusDot verdict={spec.status} />
        <h1 className="min-w-0 font-mono text-2xl">{spec.slug}</h1>
      </div>
      {spec.claim && <p className="mt-4 max-w-3xl leading-relaxed text-dim">{spec.claim}</p>}

      <dl className="mt-8 grid grid-cols-1 gap-4 border border-line bg-surface/40 p-6 md:grid-cols-2">
        {[
          ["UNIVERSE", spec.universe.join(", ")],
          ["BAR", spec.bar],
          ["DIRECTION", spec.direction],
          ["SIGNAL", spec.signal],
          ["ENTRY", spec.entry],
          ["EXIT", spec.exit],
        ].map(([k, v]) => (
          <div key={k as string}>
            <dt className="font-mono text-[11px] tracking-widest text-dim">{k}</dt>
            <dd className="mt-1 font-mono text-sm text-ink">{v || "—"}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        {run && (
          <Link to={`/workspace/backtests/${slug}`} className="font-mono text-xs text-accent">
            view latest backtest report →
          </Link>
        )}
        {rawTruncated ? (
          <p className="font-mono text-xs text-dim">
            Specification preview is truncated. Use the full YAML from the repository.
          </p>
        ) : <CopyButton text={spec.raw} label="spec YAML" />}
      </div>

      <details className="mt-6 border border-line">
        <summary className="cursor-pointer px-4 py-2 font-mono text-xs text-dim">
          specs/{slug}.yaml
        </summary>
        <pre className="max-h-96 overflow-auto p-4 font-mono text-xs leading-relaxed text-ink/90">
          {spec.raw}
        </pre>
      </details>
      {code && <p className="mt-4 font-mono text-[11px] text-dim">{code}</p>}
    </div>
  );
}

export default function Lab() {
  return (
    <div>
      <h1 className="text-4xl font-light">Strategy Lab</h1>
      <p className="mt-3 max-w-2xl text-sm text-dim">
        Explicit specifications — universe, signal, rules, costs — before any code exists.
      </p>
      {workspace.specs.length === 0 ? (
        <p className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          No specs yet — run extract.py on triaged ideas.
        </p>
      ) : (
        <ol className="mt-8 border-t border-line">
          {workspace.specs.map((s) => (
            <li key={s.slug} className="border-b border-line">
              <Link to={`/workspace/lab/${s.slug}`}
                    className="block py-5 transition-colors hover:bg-surface/60">
                <div className="flex min-w-0 flex-col items-start gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                  <span className="max-w-full min-w-0 truncate font-mono text-sm">{s.slug}</span>
                  <span className="min-w-0 max-w-full break-words font-mono text-[11px] text-dim">
                    {s.universe.join(" / ") || "—"}
                  </span>
                </div>
                {s.claim && (
                  <p className="mt-1 line-clamp-1 max-w-3xl text-sm text-dim">{s.claim}</p>
                )}
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
