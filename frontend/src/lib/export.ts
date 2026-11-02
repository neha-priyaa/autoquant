/** Dependency-free client-side exports (#42). Downloads happen via a Blob +
 * anchor click — no network, no server. */

export function exportToCsv(
  filename: string,
  headers: string[],
  rows: (string | number | boolean | null | undefined)[][],
): void {
  const cell = (v: string | number | boolean | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.map(cell).join(","), ...rows.map(r => r.map(cell).join(","))];
  download(`${filename}.csv`, lines.join("\n"), "text/csv");
}

export function exportToJson(filename: string, data: unknown): void {
  download(`${filename}.json`, JSON.stringify(data, null, 2), "application/json");
}

function download(filename: string, content: string, mime: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
