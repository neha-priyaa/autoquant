import { useCallback, useEffect, useState } from "react";

export type Theme = "dark" | "light" | "terminal" | "amber";
export const THEME_ORDER: Theme[] = ["dark", "light", "terminal", "amber"];
const KEY = "aq-theme";

const isTheme = (v: string | undefined | null): v is Theme =>
  !!v && (THEME_ORDER as string[]).includes(v);

/** Theme state lives on <html data-theme> (pre-paint inline script in
 * index.html prevents a flash); this hook mirrors it into React and
 * persists the choice. Dark is the default. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() =>
    isTheme(document.documentElement.dataset.theme)
      ? (document.documentElement.dataset.theme as Theme)
      : "dark",
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((t) => THEME_ORDER[(THEME_ORDER.indexOf(t) + 1) % THEME_ORDER.length]);
  }, []);
  return { theme, toggle };
}
