export default function Footer() {
  return (
    <footer className="border-t border-line px-6 py-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="font-mono text-sm tracking-[0.3em]">AUTOQUANT</div>
          <p className="mt-3 max-w-md text-sm text-dim">
            Historical backtests are research evidence, not guarantees of
            future performance. Every number on this site is reproducible
            from the repository.
          </p>
        </div>
        <div className="font-mono text-xs text-dim">
          harvest → fetch → triage → spec → codegen → backtest → leaderboard
        </div>
      </div>
    </footer>
  );
}
