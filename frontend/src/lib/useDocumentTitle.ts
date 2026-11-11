import { useEffect } from "react";

const DEFAULT_TITLE = "AutoQuant — research the idea. test the evidence.";

/** Sets the browser tab title while mounted (SPA routes share one title
 * otherwise, so tabs and screen readers can't tell pages apart). Restores
 * the previous title on unmount so returning to the landing page resets it. */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} — AutoQuant` : DEFAULT_TITLE;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
