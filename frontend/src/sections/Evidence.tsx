import { Reveal } from "../components/Reveal";
import { MetricReadout } from "../components/MetricReadout";
import { snapshot, type Headline } from "../content/snapshot";

export default function Evidence({ headline }: { headline?: Headline | null }) {
  const h = headline === undefined ? snapshot.headline : headline;
  return (
    <section id="evidence" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal>
        <h2 className="max-w-3xl text-4xl font-light leading-tight md:text-6xl">
          Evidence over assumptions.
        </h2>
        <p className="mt-6 max-w-xl text-dim">
          Every strategy survives the same gauntlet: explicit rules, real price
          history, explicit costs, and a null model. Historical backtests are
          research evidence, not guarantees.
        </p>
      </Reveal>
      {h ? (
        <Reveal className="mt-16">
          <div className="border border-line bg-surface/50 p-8">
            <div className="font-mono text-xs tracking-widest text-dim">
              LATEST RUN — {h.slug}
            </div>
            <div className="mt-8 grid grid-cols-2 gap-8 md:grid-cols-4">
              {h.metrics.slice(0, 8).map((m) => (
                <MetricReadout key={m.label} label={m.label} value={m.strategy} />
              ))}
            </div>
            <p className="mt-8 font-mono text-[11px] text-dim">
              strategy column, net of costs — full tables in reports/{h.slug}.md
            </p>
          </div>
        </Reveal>
      ) : (
        <Reveal className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          No completed backtest runs yet — the evidence panel fills in from
          reports/ once the pipeline has run.
        </Reveal>
      )}
    </section>
  );
}
