import { Link } from "react-router-dom";

export default function FinalCta() {
  return (
    <section className="relative overflow-hidden border-t border-line px-6 py-40 text-center">
      <div className="gridlines pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mx-auto max-w-3xl">
        <h2 className="text-4xl font-light leading-tight md:text-6xl">
          Good research starts with
          <br />
          <span className="text-dim">a testable question.</span>
        </h2>
        <Link
          to="/workspace"
          className="mt-12 inline-block bg-accent px-8 py-4 font-mono text-xs font-medium tracking-widest text-bg transition-opacity hover:opacity-85"
        >
          OPEN THE WORKSPACE
        </Link>
      </div>
    </section>
  );
}
