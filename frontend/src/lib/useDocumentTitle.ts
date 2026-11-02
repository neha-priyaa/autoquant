import { useEffect } from "react";

/** Sets the browser tab title while mounted (SPA routes share one title
 * otherwise, so tabs and screen readers can't tell pages apart). */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    if (title) document.title = `${title} — AutoQuant`;
    else document.title = "AutoQuant — research the idea. test the evidence.";
  }, [title]);
}
