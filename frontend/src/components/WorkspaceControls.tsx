import { ArrowLeft, BookOpen, Binary, Feather, Glasses, Moon, Sparkles, Square, Sun, Terminal, Zap } from "lucide-react";
import { NavLink } from "react-router-dom";
import type { Mode, Theme } from "../lib/theme";

const THEME_ICON: Record<Theme, typeof Moon> = {
  dark: Moon,
  light: Sun,
  terminal: Terminal,
  amber: Zap,
  ivory: Feather,
  noir: Sparkles,
  brutal: Square,
  zenburn: BookOpen,
  matrix: Binary,
  "cb-dark": Glasses,
  "cb-light": Glasses,
};

/** Theme, skin, and landing controls shared by the desktop sidebar and the
 * mobile workspace bar (#39). */
export default function WorkspaceControls({
  theme,
  mode,
  onToggleMode,
  onCycleTheme,
}: {
  theme: Theme;
  mode: Mode;
  onToggleMode: () => void;
  onCycleTheme: () => void;
}) {
  const ThemeIcon = THEME_ICON[theme];
  return (
    <>
      <button
        onClick={onToggleMode}
        aria-label={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}
        title={`mode: ${mode} — like your phone's dark mode`}
        className="flex items-center gap-3 px-2 py-2 text-sm text-dim transition-colors hover:text-ink"
      >
        {mode === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        {mode === "dark" ? "Light mode" : "Dark mode"}
      </button>
      <button
        onClick={onCycleTheme}
        aria-label={`Cycle skin (current: ${theme})`}
        title={`skin: ${theme} — click to cycle`}
        className="flex items-center gap-3 px-2 py-2 text-sm text-dim transition-colors hover:text-ink"
      >
        <ThemeIcon className="h-4 w-4" />
        <span className="capitalize">{theme} skin</span>
      </button>
      <NavLink to="/" className="flex items-center gap-3 px-2 py-2 text-sm text-dim transition-colors hover:text-ink">
        <ArrowLeft className="h-4 w-4" /> Landing
      </NavLink>
    </>
  );
}
