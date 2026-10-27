import { useMemo, useState } from "react";
import { workspace } from "../../content/workspace";

export default function Triage() {
  const [minScore, setMinScore] = useState(0);
  const rows = useMemo(
    () =>
      [...workspace.triage]
        .filter((t) => (t.score ?? -1) >= minScore)
        .sort((a, b) => (b.score ?? -1) - (a.score ?? -1)),
    [minScore],
  );

  return (
    <div>
      <h1 className="text-4xl font-light">Idea Triage</h1>
      <p className="mt-3 max-w-2xl text-sm text-dim">
        Every score below is an <strong className="text-ink">LLM assessment</strong> of
        testability — it is not a backtest result and carries no performance evidence.
      </p>

      <label className="mt-6 flex items-center gap-3 font-mono text-xs text-dim">
        MIN SCORE {minScore}
        <input type="range" min={0} max={5} value={minScore}
               onChange={(e) => setMinScore(Number(e.target.value))}
               className="accent-accent" aria-label="Minimum triage score" />
        <span className="ml-auto">{rows.length} IDEAS</span>
      </label>

      {rows.length === 0 ? (
        <p className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          {workspace.triage.length === 0
            ? "Nothing triaged yet — run triage.py, then regenerate the snapshot."
            : "No ideas match the minimum score — lower the filter to see more."}
        </p>
      ) : (
        <ol className="mt-8 space-y-4">
          {rows.map((t) => (
            <li key={t.slug} className="border border-line bg-surface/40 p-6">
              <div className="flex items-baseline justify-between gap-4">
                <h2 className="min-w-0 text-lg font-light">{t.title}</h2>
                <span className="shrink-0 font-mono text-2xl tabular-nums text-accent">
                  {t.score ?? "—" }
                  <span className="text-xs text-dim">/5</span>
                </span>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-relaxed text-dim">{t.claim}</p>
              {t.reason && (
                <p className="mt-2 max-w-3xl font-mono text-[11px] text-dim">why: {t.reason}</p>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                {t.assetClass && (
                  <span className="border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-dim">
                    {t.assetClass}
                  </span>
                )}
                {t.redFlags.map((f) => (
                  <span key={f} className="border border-fail/50 px-2 py-0.5 font-mono text-[10px] text-fail">
                    flag: {f}
                  </span>
                ))}
                {t.missing.map((m) => (
                  <span key={m} className="border border-line px-2 py-0.5 font-mono text-[10px] text-dim">
                    missing: {m}
                  </span>
                ))}
                <span className="ml-auto font-mono text-[10px] uppercase tracking-widest text-dim/70">
                  llm assessment — not a backtest
                </span>
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
