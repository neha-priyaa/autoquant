/** Dependency-free client-side exports (#42). Downloads happen via a Blob +
 * anchor click — no network, no server. */

export function exportToCsv(
  filename: string,
  headers: string[],
  rows: (string | number | boolean | null | undefined)[][],
): void {
  const safe = (s: string) =>
    /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  const cell = (v: string | number | boolean | null | undefined) => {
    // CSV injection: a leading =/+/-/@ would evaluate as a spreadsheet
    // formula — prefix with an apostrophe (quoted again if it needs it)
    if (typeof v === "string" && /^[=+\-@]/.test(v)) return safe("'" + v);
    const s = v === null || v === undefined ? "" : String(v);
    return safe(s);
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
  // Attach before clicking (some browsers ignore detached anchors) and
  // revoke after the click has been dispatched so the download is not cancelled.
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
