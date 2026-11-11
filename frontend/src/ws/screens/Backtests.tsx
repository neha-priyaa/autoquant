import { Link } from "react-router-dom";
import { StatusDot } from "../../components/StatusDot";
import CliSnippet from "../../components/CliSnippet";
import TableScrollWrapper from "../../components/TableScrollWrapper";
import { workspace, newestRuns } from "../../content/workspace";
import { useDocumentTitle } from "../../lib/useDocumentTitle";

export function BacktestDetail({ slug }: { slug: string }) {
  useDocumentTitle(`${slug} — Backtest Report`);
  const report = workspace.reports[slug];
  const run = newestRuns(workspace.runs).find((r) => r.slug === slug && r.lane === "article");
  if (!report && !run) {
    return <p className="mt-10 text-dim">No backtest run found for {slug}.</p>;
  }
  return (
    <div>
      <div className="flex items-center gap-3">
        <StatusDot verdict={run?.status ?? null} />
        <h1 className="min-w-0 font-mono text-2xl">{slug}</h1>
        <span className="font-mono text-xs text-dim">{run?.lane} lane · {run?.date}</span>
      </div>

      {run?.flags?.length ? (
        <ul className="mt-4 space-y-1">
          {run.flags.map((f) => (
            <li key={f} className="font-mono text-xs text-dim">· {f}</li>
          ))}
        </ul>
      ) : null}
      {run?.error && (
        <p className="mt-4 border border-fail/50 p-3 font-mono text-xs text-fail">
          {run.error}
        </p>
      )}

      {report && (
        <>
          <p className="mt-6 text-sm text-dim">Latest report for this strategy. Historical report versions are not retained.</p>
          <div className="mt-8 border border-line">
            <TableScrollWrapper>
            <table className="w-full text-left font-mono text-sm">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-widest text-dim">
                  <th className="px-4 py-2">Metric</th>
                  <th className="px-4 py-2">Strategy</th>
                  <th className="px-4 py-2">Buy &amp; hold</th>
                </tr>
              </thead>
              <tbody>
                {report.metrics.map((m) => (
                  <tr key={m.label} className="border-b border-line/60">
                    <td className="px-4 py-2 text-dim">{m.label}</td>
                    <td className="px-4 py-2 tabular-nums text-ink">{m.strategy}</td>
                    <td className="px-4 py-2 tabular-nums text-dim">{m.benchmark}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </TableScrollWrapper>
          </div>
          <details className="mt-6 border border-line" open>
            <summary className="cursor-pointer px-4 py-2 font-mono text-xs text-dim">
              full report — reports/{slug}.md
            </summary>
            <pre
              tabIndex={0}
              role="region"
              aria-label="Backtest report preview"
              className="max-h-[32rem] overflow-auto border border-line bg-surface/50 p-4 font-mono text-xs leading-relaxed text-ink/90 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent"
            >
              {report.text}
            </pre>
          </details>
        </>
      )}
      {!report && (
        <p className="mt-8 text-sm text-dim">
          No report text in the snapshot for this run — regenerate the snapshot
          after the pipeline writes reports/{slug}.md.
        </p>
      )}
    </div>
  );
}

export default function Backtests() {
  useDocumentTitle("Backtests");
  const runs = newestRuns(workspace.runs);
  return (
    <div>
      <h1 className="text-4xl font-light">Backtests</h1>
      {runs.length === 0 ? (
        <div className="mt-16">
          <CliSnippet command="uv run python backtest_batch.py && uv run python scripts/web_snapshot.py" description="No runs yet — backtest_batch.py writes the leaderboard and reports." />
        </div>
      ) : (
        <ol className="mt-8 border-t border-line">
          {runs.map((r, index) => (
            <li key={`${r.lane}-${r.slug}-${r.runAt ?? r.date}-${index}`} className="border-b border-line">
              {r.lane === "article" ? (
                <Link to={`/workspace/backtests/${r.slug}`}
                      aria-label={`${r.slug} — view latest report`}
                      className="flex items-center gap-4 py-4 transition-colors hover:bg-surface/60">
                  <StatusDot verdict={r.status} />
                  <span className="min-w-0 flex-1 truncate font-mono text-sm">{r.slug}</span>
                  <span className="hidden font-mono text-xs tabular-nums text-dim sm:block">
                    {r.netSharpe !== null ? `sharpe ${r.netSharpe.toFixed(2)}` : "—"}
                  </span>
                  <span className="font-mono text-[11px] text-dim">{r.date}</span>
                </Link>
              ) : (
                <div className="flex items-center gap-4 py-4">
                  <StatusDot verdict={r.status} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-sm">{r.slug}</span>
                    {r.error && (
                      <span className="block truncate font-mono text-[11px] text-dim">
                        {r.error}
                      </span>
                    )}
                  </span>
                  <span className="hidden font-mono text-[11px] text-dim sm:block">
                    external repo run
                  </span>
                  <span className="font-mono text-[11px] text-dim">{r.date}</span>
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
