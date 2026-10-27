const OK = new Set(["ok", "pass", "coded"]);
const FAIL = new Set(["error", "timeout", "fail"]);

export function StatusDot({
  verdict,
  label,
}: {
  verdict: string | null;
  label?: string;
}) {
  const v = (verdict ?? "").toLowerCase();
  const cls =
    OK.has(v) ? "bg-accent" : FAIL.has(v) ? "bg-fail" : "bg-dim";
  return (
    <span
      className="inline-flex items-center gap-2"
      aria-label={`status ${verdict ?? "unknown"}`}
    >
      <span aria-hidden className={`inline-block h-1.5 w-1.5 rounded-full ${cls}`} />
      {label && <span className="font-mono text-xs text-dim">{label}</span>}
    </span>
  );
}
