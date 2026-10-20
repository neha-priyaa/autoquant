import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

export default function WorkspaceStub() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6">
      <div className="font-mono text-xs tracking-widest text-dim">/WORKSPACE</div>
      <h1 className="mt-4 text-5xl font-light leading-tight">
        The research terminal is under construction.
      </h1>
      <p className="mt-6 max-w-xl text-dim">
        The workspace screens (research feed, triage, strategy lab, backtest
        explorer, leaderboard) are the next build slice. Today you can inspect
        every artifact directly in the repository: reports live in{" "}
        <code className="font-mono text-ink">reports/</code>, the leaderboard in{" "}
        <code className="font-mono text-ink">results/leaderboard.jsonl</code>, and
        strategy specs in <code className="font-mono text-ink">specs/</code>.
      </p>
      <Link
        to="/"
        className="mt-8 inline-flex w-fit items-center gap-2 font-mono text-sm text-accent"
      >
        <ArrowLeft className="h-4 w-4" /> Back to the landing
      </Link>
    </main>
  );
}
