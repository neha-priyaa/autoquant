import { NavLink, Outlet } from "react-router-dom";
import {
  ArrowLeft, BarChart3, FlaskConical, LayoutDashboard,
  Library, ListFilter, Newspaper, Trophy,
} from "lucide-react";
import { useTheme } from "../lib/theme";
import { Moon, Sun } from "lucide-react";

const TABS = [
  { to: "/workspace", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/workspace/feed", label: "Feed", icon: Newspaper },
  { to: "/workspace/triage", label: "Triage", icon: ListFilter },
  { to: "/workspace/lab", label: "Strategy Lab", icon: FlaskConical },
  { to: "/workspace/backtests", label: "Backtests", icon: BarChart3 },
  { to: "/workspace/leaderboard", label: "Leaderboard", icon: Trophy },
  { to: "/workspace/catalog", label: "Catalog", icon: Library },
];

export default function Shell() {
  const { theme, toggle } = useTheme();
  const tab = (t: (typeof TABS)[number], mobile = false) => (
    <NavLink
      key={t.to}
      to={t.to}
      end={t.end}
      className={({ isActive }) =>
        mobile
          ? `whitespace-nowrap border px-3 py-2 font-mono text-[11px] tracking-widest transition-colors ${
              isActive ? "border-accent text-accent" : "border-line text-dim"}`
          : `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
              isActive ? "bg-surface text-ink" : "text-dim hover:text-ink"}`
      }
    >
      <t.icon className="h-4 w-4" />
      {t.label}
    </NavLink>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-line px-3 py-6 md:flex">
        <NavLink to="/" className="mb-8 px-4 font-mono text-sm tracking-[0.3em]">
          AUTOQUANT
        </NavLink>
        <nav aria-label="Workspace" className="flex flex-col gap-1">
          {TABS.map((t) => tab(t))}
        </nav>
        <div className="mt-auto flex flex-col gap-1 px-2">
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="flex items-center gap-3 px-2 py-2 text-sm text-dim transition-colors hover:text-ink"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
          <NavLink to="/" className="flex items-center gap-3 px-2 py-2 text-sm text-dim transition-colors hover:text-ink">
            <ArrowLeft className="h-4 w-4" /> Landing
          </NavLink>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <div className="flex gap-2 overflow-x-auto border-b border-line p-3 md:hidden">
          {TABS.map((t) => tab(t, true))}
        </div>
        <main className="mx-auto max-w-6xl px-6 py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
