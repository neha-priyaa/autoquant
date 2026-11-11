import { useMemo, useState } from "react";
import { workspace, type Article } from "../../content/workspace";
import { useDocumentTitle } from "../../lib/useDocumentTitle";
import { useQueryState } from "../../lib/useQueryState";
import { httpUrl } from "../../content/urls";
import CliSnippet from "../../components/CliSnippet";

const STAGES = ["all", "discovered", "fetched", "triaged", "processed"];

export default function Feed() {
  useDocumentTitle("Research Feed");
  const [q, setQ] = useQueryState("q", "");
  const [stage, setStage] = useQueryState("stage", "all");
  const [source, setSource] = useQueryState("source", "all");
  const [open, setOpen] = useState<Article | null>(null);
  const sources = useMemo(
    () => [...new Set(workspace.articles
      .map((a) => a.source)
      .filter((s): s is string => !!s))].sort(),
    [],
  );

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return workspace.articles.filter(
      (a) =>
        (stage === "all" || (a.stage ?? "").includes(stage)) &&
        (source === "all" || a.source === source) &&
        (!needle ||
          `${a.title} ${a.source} ${a.slug}`.toLowerCase().includes(needle)),
    );
  }, [q, stage, source]);

  return (
    <div>
      <h1 className="text-4xl font-light">Research Feed</h1>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search title or source…"
          aria-label="Search articles"
          className="w-72 max-w-full border border-line bg-bg px-3 py-2 font-mono text-sm text-ink placeholder:text-dim/60"
        />
        <div role="group" aria-label="Stage filter" className="flex flex-wrap gap-2">
          {STAGES.map((s) => (
            <button key={s} onClick={() => setStage(s)}
              aria-pressed={stage === s}
              className={`border px-3 py-2 font-mono text-[11px] tracking-widest transition-colors ${
                stage === s ? "border-accent text-accent" : "border-line text-dim hover:text-ink"}`}>
              {s.toUpperCase()}
            </button>
          ))}
        </div>
        <label className="font-mono text-xs text-dim">
          SOURCE{" "}
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            aria-label="Source filter"
            className="ml-2 border border-line bg-bg px-3 py-2 font-mono text-xs text-ink"
          >
            <option value="all">ALL</option>
            {sources.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>
        <span className="ml-auto font-mono text-xs text-dim">{rows.length} ARTICLES</span>
      </div>

      {rows.length === 0 ? (
        workspace.articles.length === 0 ? (
          <div className="mt-16">
            <CliSnippet
              command="uv run python harvest.py && uv run python scripts/web_snapshot.py"
              label="No articles yet — run harvest.py, then regenerate the snapshot."
            />
          </div>
        ) : (
          <p className="mt-16 border border-dashed border-line p-12 text-center text-dim">
            No articles match — clear the search or filters.
          </p>
        )
      ) : (
        <ol className="mt-8 border-t border-line">
          {rows.map((a, index) => {
            const url = httpUrl(a.url);
            return (
              <li key={`${a.slug ?? a.url ?? "article"}-${index}`} className="border-b border-line">
                <button className="w-full py-5 text-left transition-colors hover:bg-surface/60"
                  aria-expanded={open === a}
                  onClick={() => setOpen(open === a ? null : a)}>
                  <div className="flex items-baseline justify-between gap-6">
                    <h2 className="min-w-0 truncate text-lg font-light">{a.title}</h2>
                    <span className="shrink-0 font-mono text-[11px] text-dim">
                      {a.source} · {a.posted?.slice(0, 10)}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-3">
                    <span className="border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-dim">
                      {a.stage ?? "unknown"}
                    </span>
                    {a.triageScore !== null && (
                      <span className="font-mono text-[11px] text-dim">
                        triage {a.triageScore}/5
                      </span>
                    )}
                  </div>
                </button>
                {open === a && (
                  <div className="pb-6">
                    <p className="max-w-3xl text-sm leading-relaxed text-dim">{a.blurb}</p>
                    {url && <a href={url} target="_blank" rel="noreferrer"
                       className="mt-3 inline-block font-mono text-xs text-accent">
                      read the source article →
                    </a>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
