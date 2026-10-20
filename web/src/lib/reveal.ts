import { useEffect, useRef } from "react";

/** Adds .in to .reveal elements when they enter the viewport. One global
 * observer per landing mount; reduced-motion users get .in immediately via
 * the CSS override in tokens.css. */
export function useRevealRoot() {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const root = ref.current;
    if (!root) return;
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
      { threshold: 0.15 },
    );
    root.querySelectorAll(".reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
  return ref;
}
