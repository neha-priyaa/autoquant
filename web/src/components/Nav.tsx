import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react";
import { useTheme } from "../lib/theme";

const LINKS: [string, string][] = [
  ["Product", "#product"],
  ["Pipeline", "#pipeline"],
  ["Experiments", "#experiments"],
  ["Documentation", "https://github.com/uberdeveloper/autoquant#readme"],
];

export default function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const { theme, toggle } = useTheme();
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`fixed inset-x-0 top-0 z-50 border-b transition-colors ${
        scrolled ? "border-line bg-bg/85 backdrop-blur" : "border-transparent"
      }`}
    >
      <nav
        className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4"
        aria-label="Main"
      >
        <Link to="/" className="font-mono text-sm font-medium tracking-[0.3em]">
          AUTOQUANT
        </Link>
        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map(([label, href]) => (
            <a
              key={label}
              href={href}
              className="text-sm text-dim transition-colors hover:text-ink"
            >
              {label}
            </a>
          ))}
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="text-dim transition-colors hover:text-ink"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <Link
            to="/workspace"
            className="border border-line px-4 py-2 font-mono text-xs tracking-widest text-accent transition-colors hover:border-accent"
          >
            OPEN WORKSPACE <ArrowUpRight className="ml-1 inline h-3 w-3" />
          </Link>
        </div>
        <div className="flex items-center gap-4 md:hidden">
          <button onClick={toggle} aria-label="Toggle theme" className="text-dim">
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
          <button aria-label="Menu" onClick={() => setOpen(!open)}>
            {open ? <X /> : <Menu />}
          </button>
        </div>
      </nav>
      {open && (
        <div className="border-t border-line bg-bg px-6 py-8 md:hidden">
          {LINKS.map(([label, href]) => (
            <a
              key={label}
              href={href}
              onClick={() => setOpen(false)}
              className="block py-3 text-2xl text-ink"
            >
              {label}
            </a>
          ))}
          <Link
            to="/workspace"
            onClick={() => setOpen(false)}
            className="mt-4 block font-mono text-sm text-accent"
          >
            OPEN WORKSPACE →
          </Link>
        </div>
      )}
    </header>
  );
}
