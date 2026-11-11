import { useEffect, useRef, useState, type ReactNode } from "react";

/** Which scroll indicators should show for a scrollable container.
 * Pure so it is unit-testable (jsdom has no layout). */
export function overflowState(
  scrollWidth: number,
  clientWidth: number,
  scrollLeft: number,
): { left: boolean; right: boolean } {
  const scrollable = scrollWidth > clientWidth + 1;
  return {
    left: scrollable && scrollLeft > 1,
    right: scrollable && scrollLeft < scrollWidth - clientWidth - 1,
  };
}

/** Horizontal-scroll container with a "scroll →" affordance (#45): on
 * narrow screens users otherwise can't tell columns continue off-screen. */
export default function TableScrollWrapper({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState({ left: false, right: false });

  const update = () => {
    const el = ref.current;
    if (el) setState(overflowState(el.scrollWidth, el.clientWidth, el.scrollLeft));
  };
  useEffect(() => {
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  return (
    <div className="relative">
      <div ref={ref} className="overflow-x-auto" onScroll={update}>
        {children}
      </div>
      {state.right && (
        <>
          <div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 right-0 w-10 sm:hidden bg-gradient-to-l from-bg/90 to-transparent"
          />
          <span
            aria-hidden
            className="pointer-events-none absolute right-2 top-1/2 sm:hidden -translate-y-1/2 font-mono text-[10px] text-dim"
          >
            scroll →
          </span>
        </>
      )}
    </div>
  );
}
