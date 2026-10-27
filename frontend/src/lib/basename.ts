/** Router basename from Vite's injected base. GitHub Pages serves the site
 * under /autoquant/ — without this, BrowserRouter sees /autoquant/ as the
 * pathname, matches no route, and renders an empty main (the "broken page"). */
export function normalizeBasename(base: string): string {
  const trimmed = base.replace(/\/$/, "");
  return trimmed === "" ? "/" : trimmed;
}
