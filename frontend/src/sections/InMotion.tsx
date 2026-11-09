import { useState } from "react";
import { Reveal } from "../components/Reveal";
import { snapshot, type Chain } from "../content/snapshot";

const LABEL: Record<string, string> = {
  article: "01 · SOURCE ARTICLE",
  spec: "02 · STRATEGY SPEC",
  code: "03 · GENERATED CODE",
  report: "04 · BACKTEST REPORT",
};

export default function InMotion({ chain }: { chain?: Chain | null }) {
  const c = chain === undefined ? (snapshot.chains[0] ?? null) : chain;
  const [step, setStep] = useState(0);
  if (!c || c.stages.length === 0) {
    return (
      <section id="motion" className="border-y border-line px-6 py-32">
        <div className="mx-auto max-w-6xl">
          <p className="font-mono text-xs tracking-widest text-dim">
            RESEARCH IN MOTION
          </p>
          <p className="mt-6 max-w-xl text-dim">
            No completed experiment chains yet — run the pipeline and
            regenerate the snapshot ({" "}
            <code className="font-mono text-ink">
              uv run python scripts/web_snapshot.py
            </code>
            ).
          </p>
        </div>
      </section>
    );
  }
  const stage = c.stages[step] ?? c.stages[0];
  return (
    <section id="motion" className="border-y border-line bg-surface/30 px-6 py-32">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <p className="font-mono text-xs tracking-widest text-dim">
            RESEARCH IN MOTION
          </p>
          <h2 className="mt-4 max-w-2xl text-4xl font-light md:text-5xl">
            {c.title}
          </h2>
        </Reveal>
        <div role="tablist" aria-label="Artifact stages" className="mt-12 flex flex-wrap gap-2">
          {c.stages.map((s, i) => (
            <button
              key={s.kind}
              role="tab"
              aria-selected={i === step}
              onClick={() => setStep(i)}
              className={`border px-4 py-2 font-mono text-[11px] tracking-widest transition-colors ${
                i === step ? "border-accent text-accent" : "border-line text-dim hover:text-ink"
              }`}
            >
              {LABEL[s.kind] ?? s.kind}
            </button>
          ))}
        </div>
        <div className="mt-6 border border-line bg-bg">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <span className="font-mono text-xs text-dim">{stage.title}</span>
            <a
              href={`https://github.com/uberdeveloper/autoquant/blob/main/${stage.repoPath}`}
              className="font-mono text-[11px] text-dim hover:text-accent"
            >
              inspect in repo →
            </a>
          </div>
          <pre className="max-h-[28rem] overflow-auto p-6 font-mono text-xs leading-relaxed text-ink/90">
            {stage.body}
          </pre>
        </div>
      </div>
    </section>
  );
}
