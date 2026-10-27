import { Reveal } from "../components/Reveal";
import { snapshot, type Stage } from "../content/snapshot";

export default function Pipeline({ stages }: { stages?: Stage[] }) {
  const rows = stages ?? snapshot.stages;
  return (
    <section id="pipeline" className="mx-auto max-w-6xl px-6 py-32">
      <Reveal>
        <p className="font-mono text-xs tracking-widest text-dim">THE PIPELINE</p>
        <h2 className="mt-4 max-w-2xl text-4xl font-light md:text-6xl">
          From idea to evidence,
          <br />
          <span className="text-dim">seven honest stages.</span>
        </h2>
      </Reveal>
      {rows.length === 0 ? (
        <Reveal className="mt-16 border border-dashed border-line p-12 text-center text-dim">
          Pipeline manifest unavailable — regenerate the snapshot.
        </Reveal>
      ) : (
        <ol className="mt-20 border-t border-line">
          {rows.map((s) => (
            <Reveal key={s.index}>
              <li className="group relative border-b border-line py-8 transition-colors hover:bg-surface/60">
                <a
                  href={s.doc}
                  className="mx-auto grid max-w-6xl grid-cols-[auto_1fr] items-baseline gap-6 px-2 md:grid-cols-[80px_1fr_auto]"
                >
                  <span className="font-mono text-sm text-dim transition-colors group-hover:text-accent">
                    {s.index}
                  </span>
                  <div>
                    <h3 className="text-2xl font-light">{s.name}</h3>
                    <p className="mt-1 max-w-xl text-sm text-dim">{s.description}</p>
                  </div>
                  <span className="hidden font-mono text-xs text-dim/70 md:block">
                    {s.artifact}
                  </span>
                </a>
              </li>
            </Reveal>
          ))}
        </ol>
      )}
    </section>
  );
}
