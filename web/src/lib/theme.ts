import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light";
const KEY = "aq-theme";

/** Theme state lives on <html data-theme> (pre-paint inline script in
 * index.html prevents a flash); this hook mirrors it into React and
 * persists the choice. Dark is the default. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "light" ? "light" : "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    [],
  );
  return { theme, toggle };
}
