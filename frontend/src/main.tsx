import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Outlet, Link, useParams } from "react-router-dom";
import "./styles/tokens.css";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import Hero from "./sections/Hero";
import Pipeline from "./sections/Pipeline";
import InMotion from "./sections/InMotion";
import Evidence from "./sections/Evidence";
import Archive from "./sections/Archive";
import FinalCta from "./sections/FinalCta";
import { lazy, Suspense } from "react";
import Shell from "./ws/Shell";

const Overview = lazy(() => import("./ws/screens/Overview"));
const Feed = lazy(() => import("./ws/screens/Feed"));
const Triage = lazy(() => import("./ws/screens/Triage"));
const Lab = lazy(() => import("./ws/screens/Lab"));
const Backtests = lazy(() => import("./ws/screens/Backtests"));
const Leaderboard = lazy(() => import("./ws/screens/Leaderboard"));
const CatalogScreen = lazy(() => import("./ws/screens/CatalogScreen"));
const SpecDetail = lazy(() =>
  import("./ws/screens/Lab").then((m) => ({ default: m.SpecDetail })));
const BacktestDetail = lazy(() =>
  import("./ws/screens/Backtests").then((m) => ({ default: m.BacktestDetail })));

function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center px-6">
      <div className="font-mono text-xs tracking-widest text-dim">404</div>
      <h1 className="mt-4 text-5xl font-light">This page doesn&apos;t exist.</h1>
      <p className="mt-4 text-dim">The research workspace has: Overview, Feed,
        Triage, Strategy Lab, Backtests, Leaderboard, Catalog.</p>
      <p className="mt-6"><Link to="/" className="underline">Home</Link></p>
    </main>
  );
}

function SuspenseFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <span className="font-mono text-xs tracking-widest text-dim">LOADING…</span>
    </div>
  );
}
import { useRevealRoot } from "./lib/reveal";
import { normalizeBasename } from "./lib/basename";

function Landing() {
  const ref = useRevealRoot();
  return (
    <main ref={ref}>
      <Hero />
      <Pipeline />
      <InMotion />
      <Evidence />
      <Archive />
      <FinalCta />
    </main>
  );
}

function LandingLayout() {
  return <><Nav /><Landing /><Footer /></>;
}

function SpecDetailRoute() {
  const { slug } = useParams();
  return <SpecDetail slug={slug ?? ""} />;
}

function BacktestDetailRoute() {
  const { slug } = useParams();
  return <BacktestDetail slug={slug ?? ""} />;
}

export default function App() {
  return (
    <StrictMode>
      <BrowserRouter basename={normalizeBasename(import.meta.env.BASE_URL)}>
        <Routes>
          <Route path="/" element={<LandingLayout />} />
          <Route path="/workspace" element={<Shell />}>
            <Route element={<Suspense fallback={<SuspenseFallback />}><Outlet /></Suspense>}>
              <Route index element={<Overview />} />
              <Route path="feed" element={<Feed />} />
              <Route path="triage" element={<Triage />} />
              <Route path="lab" element={<Lab />} />
              <Route path="lab/:slug" element={<SpecDetailRoute />} />
              <Route path="backtests" element={<Backtests />} />
              <Route path="backtests/:slug" element={<BacktestDetailRoute />} />
              <Route path="leaderboard" element={<Leaderboard />} />
              <Route path="catalog" element={<CatalogScreen />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </StrictMode>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
