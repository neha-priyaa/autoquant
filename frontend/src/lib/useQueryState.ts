import { useSearchParams } from "react-router-dom";

/** Search/filter/sort state persisted in the URL (#40): refresh and
 * browser-back keep the view, and filtered URLs are shareable. Writes
 * replace (no history spam). Falls back when the param is absent. */
export function useQueryState(
  key: string,
  fallback: string,
): [string, (value: string) => void] {
  const [params, setParams] = useSearchParams();
  const value = params.get(key) ?? fallback;
  const setValue = (v: string) => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (v === fallback) next.delete(key);
        else next.set(key, v);
        return next;
      },
      { replace: true },
    );
  };
  return [value, setValue];
}
