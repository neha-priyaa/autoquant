export function MetricReadout({
  label,
  value,
  big = false,
}: {
  label: string;
  value: string;
  big?: boolean;
}) {
  return (
    <div>
      <div className="font-mono text-[11px] uppercase tracking-widest text-dim">
        {label}
      </div>
      <div
        className={`font-mono tabular-nums ${big ? "text-5xl" : "text-2xl"} text-ink`}
      >
        {value}
      </div>
    </div>
  );
}
