import { useCallback, useEffect, useState } from "react";

export type Mode = "dark" | "light";
export type Theme =
  | "dark" | "light" | "terminal" | "amber"
  | "ivory" | "noir" | "brutal"
  | "zenburn" | "matrix" | "cb-dark" | "cb-light";

interface ThemeDef { mode: Mode; family: string }

/** Every skin has a mode (dark/light, like a phone) and a family (its look).
 * The MODE control switches dark/light — keeping the family when it exists
 * in both modes (classic, colorblind) — and the THEME control cycles the
 * skins available in the current mode. */
export const THEMES: Record<Theme, ThemeDef> = {
  dark:     { mode: "dark",  family: "classic" },
  light:    { mode: "light", family: "classic" },
  terminal: { mode: "dark",  family: "terminal" },
  amber:    { mode: "dark",  family: "amber" },
  ivory:    { mode: "light", family: "ivory" },
  noir:     { mode: "dark",  family: "noir" },
  brutal:   { mode: "light", family: "brutal" },
  zenburn:  { mode: "dark",  family: "zenburn" },
  matrix:   { mode: "dark",  family: "matrix" },
  "cb-dark":  { mode: "dark",  family: "colorblind" },
  "cb-light": { mode: "light", family: "colorblind" },
};

export const THEME_ORDER: Theme[] = Object.keys(THEMES) as Theme[];

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

  const setMode = useCallback((mode: Mode) => {
    setTheme((t) => {
      if (THEMES[t].mode === mode) return t;
      const def = THEMES[t].family;
      const sibling = (Object.keys(THEMES) as Theme[]).find(
        (k) => THEMES[k].family === def && THEMES[k].mode === mode,
      );
      return sibling ?? (mode === "light" ? "light" : "dark");
    });
  }, []);

  const cycleTheme = useCallback(() => {
    setTheme((t) => {
      const inMode = THEME_ORDER.filter((k) => THEMES[k].mode === THEMES[t].mode);
      return inMode[(inMode.indexOf(t) + 1) % inMode.length];
    });
  }, []);

  const toggle = cycleTheme; // legacy alias
  return { theme, setMode, cycleTheme, toggle };
}
