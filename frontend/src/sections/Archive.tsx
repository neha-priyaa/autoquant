import { useState } from "react";
import { Reveal } from "../components/Reveal";
import { StatusDot } from "../components/StatusDot";
import { snapshot, type ArchiveRow } from "../content/snapshot";

type SortKey = "date" | "sharpe";
const fmt = (n: number | null) =>
  n === null || n === undefined ? "—" : n.toFixed(2);

export default function Archive({ rows: rowsProp }: { rows?: ArchiveRow[] }) {
  const [sort, setSort] = useState<SortKey>("date");
  const rows = [...(rowsProp ?? snapshot.archive)].sort((a, b) =>
    sort === "date"
      ? (Date.parse(b.runAt || b.date) || 0) - (Date.parse(a.runAt || a.date) || 0)
      : (b.netSharpe ?? -99) - (a.netSharpe ?? -99),
  );

  return (
    <section id="experiments" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal className="flex flex-wrap items-end justify-between gap-6">
        <div>
          <p className="font-mono text-xs tracking-widest text-dim">
            THE EXPERIMENT ARCHIVE
          </p>
          <h2 className="mt-4 text-4xl font-light md:text-6xl">
            Every test, <span className="text-dim">on the record.</span>
          </h2>
        </div>
        <label className="font-mono text-xs text-dim">
          RANK BY{" "}
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="ml-2 border border-line bg-bg px-3 py-2 font-mono text-xs text-ink"
          >
            <option value="date">RUN DATE</option>
            <option value="sharpe">NET SHARPE</option>
          </select>
        </label>
      </Reveal>

      {rows.length === 0 ? (
        <Reveal className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          No experiments on the leaderboard yet.
        </Reveal>
      ) : (
        <ol className="mt-16 border-t border-line">
          {rows.map((r, index) => (
            <Reveal key={`${r.lane}-${r.slug}-${r.runAt ?? r.date}-${index}`}>
              <li className="grid grid-cols-[auto_1fr_auto] items-center gap-6 border-b border-line py-5 transition-colors hover:bg-surface/60">
                <StatusDot verdict={r.status} />
                <div className="min-w-0">
                  <div className="truncate font-mono text-sm text-ink">{r.slug}</div>
                  <div className="mt-0.5 truncate font-mono text-[11px] text-dim">
                    {r.source} · {r.date}
                  </div>
                </div>
                <div className="text-right font-mono text-sm tabular-nums">
                  {fmt(r.netSharpe)}
                  <div className="font-mono text-[10px] text-dim">NET SHARPE</div>
                </div>
              </li>
            </Reveal>
          ))}
        </ol>
      )}
      <p className="mt-6 font-mono text-[11px] text-dim">
        Historical performance is not indicative of future results.
      </p>
    </section>
  );
}
