import { Link } from "react-router-dom";
import { ArrowDown } from "lucide-react";
import { snapshot } from "../content/snapshot";

const YAML_LINES = [
  "meta:",
  "  slug: spy-200dma-timing",
  "signal:",
  "  definition: close > sma200",
  "rules:",
  "  entry: cross_above",
  "  execution_price: next_open",
];
const PROSE =
  "Holding an index only while it trades above its 200-day average has " +
  "historically improved risk-adjusted returns.";

export default function Hero() {
  const n = Object.values(snapshot.counts).reduce((a, b) => a + b, 0);
  return (
    <section
      className="relative overflow-hidden px-6 pb-24 pt-40 md:pt-48"
      id="product"
    >
      <div className="gridlines pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto grid max-w-6xl gap-16 md:grid-cols-[1.2fr_1fr] md:items-center">
        <div>
          <div className="mb-8 inline-flex items-center gap-2 border border-line px-3 py-1.5 font-mono text-[11px] tracking-widest text-dim">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full bg-accent"
              aria-hidden
            />
            PIPELINE IDLE — {n} ARTIFACTS INDEXED
          </div>
          <h1 className="text-5xl font-light leading-[1.05] md:text-7xl">
            Research the idea.
            <br />
            <span className="text-dim">Test the evidence.</span>
          </h1>
          <p className="mt-8 max-w-md text-lg leading-relaxed text-dim">
            Turn quantitative research into explicit trading hypotheses,
            reproducible backtests, and evidence you can inspect.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link
              to="/workspace"
              className="bg-accent px-6 py-3 font-mono text-xs font-medium tracking-widest text-bg transition-opacity hover:opacity-85"
            >
              EXPLORE THE WORKSPACE
            </Link>
            <a
              href="#pipeline"
              className="border border-line px-6 py-3 font-mono text-xs tracking-widest text-ink transition-colors hover:border-accent"
            >
              UNDERSTAND THE PIPELINE
            </a>
          </div>
        </div>

        {/* prose -> yaml -> equity trace (illustration; live numbers below) */}
        <div className="hidden border border-line bg-surface/50 p-6 md:block" aria-hidden>
          <div className="text-sm leading-relaxed text-dim">
            <p className="prose-fade">{PROSE}</p>
          </div>
          <div className="mt-6 font-mono text-xs leading-relaxed text-accent/80">
            {YAML_LINES.map((l, i) => (
              <div
                key={i}
                className="yaml-line"
                style={{ animationDelay: `${0.9 + i * 0.18}s` }}
              >
                {l}
              </div>
            ))}
          </div>
          <svg viewBox="0 0 300 80" className="mt-6 w-full">
            <path
              d="M0,60 L30,55 L60,58 L90,44 L120,48 L150,36 L180,40 L210,28 L240,32 L270,20 L300,24"
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="1.5"
              className="curve-draw"
              style={{ animationDelay: "2.6s" }}
            />
          </svg>
          <div
            className="curve-readout mt-3 flex justify-between font-mono text-xs text-dim"
            style={{ animationDelay: "3.8s" }}
          >
            <span>SHARPE 1.06</span>
            <span>MAXDD -18%</span>
            <span>62 TRADES</span>
          </div>
          <p className="mt-3 font-mono text-[10px] text-dim/60">
            illustration of the pipeline — live numbers come from real reports
            below
          </p>
        </div>
      </div>
      <a
        href="#pipeline"
        aria-label="Scroll to pipeline"
        className="absolute bottom-8 left-1/2 -translate-x-1/2 text-dim"
      >
        <ArrowDown className="h-4 w-4 animate-bounce" />
      </a>
    </section>
  );
}
