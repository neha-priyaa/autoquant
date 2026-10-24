import { useMemo, useState } from "react";
import {
  createColumnHelper, flexRender, getCoreRowModel,
  getSortedRowModel, useReactTable, type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import { StatusDot } from "../../components/StatusDot";
import { workspace, type RunRow } from "../../content/workspace";

const helper = createColumnHelper<RunRow>();

export default function Leaderboard() {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "netSharpe", desc: true },
  ]);
  const columns = useMemo(
    () => [
      helper.accessor("status", {
        header: "Status",
        cell: (c) => <StatusDot verdict={c.getValue()} />,
      }),
      helper.accessor("slug", {
        header: "Strategy",
        cell: (c) => (
          <span className="font-mono text-sm text-ink">{c.getValue()}</span>
        ),
      }),
      helper.accessor("lane", {
        header: "Lane",
        cell: (c) => (
          <span className="font-mono text-[11px] uppercase tracking-widest text-dim">
            {c.getValue()}
          </span>
        ),
      }),
      helper.accessor("netSharpe", {
        header: "Net Sharpe",
        cell: (c) =>
          c.getValue() === null ? (
            <span className="text-dim">—</span>
          ) : (
            <span className="tabular-nums">{c.getValue()!.toFixed(2)}</span>
          ),
        sortingFn: "basic",
      }),
      helper.accessor("beatsNull", {
        header: "Beats null",
        cell: (c) =>
          c.getValue() === null ? (
            <span className="text-dim">—</span>
          ) : c.getValue() ? (
            <span className="text-accent">yes</span>
          ) : (
            <span className="text-fail">no</span>
          ),
        sortingFn: "basic",
      }),
      helper.accessor("date", {
        header: "Run date",
        cell: (c) => (
          <span className="font-mono text-[11px] text-dim">{c.getValue()}</span>
        ),
      }),
    ],
    [],
  );

  const table = useReactTable<RunRow>({
    data: workspace.runs,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div>
      <h1 className="text-4xl font-light">Leaderboard</h1>
      <p className="mt-3 max-w-2xl text-sm text-dim">
        Ranked by the selected column — an explicitly chosen, explainable metric.
        Historical performance is not indicative of future results.
      </p>
      {workspace.runs.length === 0 ? (
        <p className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          Leaderboard is empty — run backtest_batch.py.
        </p>
      ) : (
        <div className="mt-8 overflow-x-auto border border-line">
          <table className="w-full text-left font-mono text-sm">
            <thead>
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id} className="border-b border-line">
                  {hg.headers.map((h) => (
                    <th key={h.id} className="px-4 py-3">
                      <button
                        onClick={h.column.getToggleSortingHandler()}
                        className="flex items-center gap-1 text-[11px] uppercase tracking-widest text-dim hover:text-ink"
                        aria-label={`Sort by ${h.column.id}`}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {{ asc: <ArrowUp className="h-3 w-3" />, desc: <ArrowDown className="h-3 w-3" /> }[
                          h.column.getIsSorted() as string
                        ] ?? null}
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="border-b border-line/60 hover:bg-surface/40">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-2.5">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
