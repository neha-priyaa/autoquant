import { useMemo, useState } from "react";
import { workspace } from "../../content/workspace";

export default function CatalogScreen() {
  const [q, setQ] = useState("");
  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return workspace.catalog;
    return workspace.catalog.filter((c) =>
      `${c.id} ${c.title ?? ""} ${c.tags.join(" ")}`
        .toLowerCase()
        .includes(needle),
    );
  }, [q]);

  return (
    <div>
      <h1 className="text-4xl font-light">Data Catalog</h1>
      <div className="mt-6 flex flex-wrap items-center gap-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search series, tags…"
          aria-label="Search catalog"
          className="w-72 border border-line bg-bg px-3 py-2 font-mono text-sm text-ink placeholder:text-dim/60"
        />
        <span className="ml-auto font-mono text-xs text-dim">
          {rows.length} / {workspace.catalogCount} SERIES
        </span>
      </div>

      {rows.length === 0 ? (
        <p className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          {workspace.catalog.length === 0
            ? "Catalog is empty — regenerate the snapshot (catalog.json at the repo root)."
            : "No series match your search."}
        </p>
      ) : (
        <ol className="mt-8 border-t border-line">
          {rows.map((c) => (
            <li key={c.id} className="border-b border-line py-5">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <span className="font-mono text-sm text-ink">{c.id}</span>
                <span className="flex items-center gap-2">
                  <span className="border border-line px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-dim">
                    {c.provider}
                  </span>
                  {c.frequency && (
                    <span className="font-mono text-[11px] text-dim">{c.frequency}</span>
                  )}
                </span>
              </div>
              {c.title && <p className="mt-1 text-sm">{c.title}</p>}
              <div className="mt-2 flex flex-wrap gap-2">
                {c.coverageStart && (
                  <span className="font-mono text-[11px] text-dim">
                    from {c.coverageStart}
                  </span>
                )}
                {c.fallback && (
                  <span className="border border-line px-2 py-0.5 font-mono text-[10px] text-dim">
                    fallback: {c.fallback}
                  </span>
                )}
                {c.tags.map((t) => (
                  <span key={t} className="border border-line px-2 py-0.5 font-mono text-[10px] text-dim">
                    #{t}
                  </span>
                ))}
              </div>
              {c.notes && <p className="mt-2 max-w-3xl text-xs text-dim">{c.notes}</p>}
              {c.license && (
                <p className="mt-1 font-mono text-[10px] text-dim/70">{c.license}</p>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
