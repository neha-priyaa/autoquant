import { useMemo } from "react";
import {
  createColumnHelper, flexRender, getCoreRowModel,
  getSortedRowModel, useReactTable, type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp } from "lucide-react";
import { StatusDot } from "../../components/StatusDot";
import CliSnippet from "../../components/CliSnippet";
import { workspace, type RunRow } from "../../content/workspace";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useQueryState } from "../../lib/useQueryState";
import TableScrollWrapper from "../../components/TableScrollWrapper";
import { exportToCsv, exportToJson } from "../../lib/export";

const helper = createColumnHelper<RunRow>();

export default function Leaderboard() {
  useDocumentTitle("Leaderboard");
  const [sortParam, setSortParam] = useQueryState("sort", "netSharpe:desc");
  const [id, dir] = sortParam.split(":");
  // memoized: a fresh array every render would loop TanStack's state updates
  const sorting = useMemo<SortingState>(
    () => [{ id, desc: dir !== "asc" }],
    [id, dir],
  );
  const setSorting = (updater: SortingState | ((old: SortingState) => SortingState)) => {
    const next = typeof updater === "function" ? updater(sorting) : updater;
    setSortParam(next.length ? `${next[0].id}:${next[0].desc ? "desc" : "asc"}` : "netSharpe:desc");
  };
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
      helper.accessor((row) => row.netSharpe ?? undefined, {
        id: "netSharpe",
        header: "Net Sharpe",
        cell: (c) =>
          c.getValue() === undefined ? (
            <span className="text-dim">—</span>
          ) : (
            <span className="tabular-nums">{c.getValue()!.toFixed(2)}</span>
          ),
        sortingFn: "basic",
        sortUndefined: "last",
      }),
      helper.accessor((row) => row.beatsNull ?? undefined, {
        id: "beatsNull",
        header: "Beats null",
        cell: (c) =>
          c.getValue() === undefined ? (
            <span className="text-dim">—</span>
          ) : c.getValue() ? (
            <span className="text-accent">yes</span>
          ) : (
            <span className="text-fail">no</span>
          ),
        sortingFn: "basic",
        sortUndefined: "last",
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

  const exportRows = table.getRowModel().rows.map((row) => row.original);

  return (
    <div>
      <h1 className="text-4xl font-light">Leaderboard</h1>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <p className="max-w-2xl text-sm text-dim">
        Ranked by the selected column — an explicitly chosen, explainable metric.
        Historical performance is not indicative of future results.
      </p>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() =>
              exportToCsv("autoquant-leaderboard",
                ["Slug", "Status", "Lane", "Net Sharpe", "Beats Null", "Run Date"],
                exportRows.map(r => [r.slug, r.status, r.lane, r.netSharpe, r.beatsNull, r.date]))}
            className="border border-line px-3 py-2 font-mono text-[11px] tracking-widest text-dim transition-colors hover:text-ink"
          >
            Export CSV
          </button>
          <button
            onClick={() => exportToJson("autoquant-leaderboard", exportRows)}
            className="border border-line px-3 py-2 font-mono text-[11px] tracking-widest text-dim transition-colors hover:text-ink"
          >
            Export JSON
          </button>
        </div>
      </div>
      {workspace.runs.length === 0 ? (
        <div className="mt-16">
          <CliSnippet command="uv run python backtest_batch.py && uv run python scripts/web_snapshot.py" description="Leaderboard is empty — run backtest_batch.py." />
        </div>
      ) : (
        <div className="mt-8 border border-line">
          <TableScrollWrapper>
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
          </TableScrollWrapper>
        </div>
      )}
    </div>
  );
}
