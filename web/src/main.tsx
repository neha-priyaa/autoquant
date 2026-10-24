import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, useParams } from "react-router-dom";
import "./styles/tokens.css";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import Hero from "./sections/Hero";
import Pipeline from "./sections/Pipeline";
import InMotion from "./sections/InMotion";
import Evidence from "./sections/Evidence";
import Archive from "./sections/Archive";
import FinalCta from "./sections/FinalCta";
import Shell from "./ws/Shell";
import Overview from "./ws/screens/Overview";
import Feed from "./ws/screens/Feed";
import Triage from "./ws/screens/Triage";
import Lab, { SpecDetail } from "./ws/screens/Lab";
import Backtests, { BacktestDetail } from "./ws/screens/Backtests";
import Leaderboard from "./ws/screens/Leaderboard";
import CatalogScreen from "./ws/screens/CatalogScreen";
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

function SpecDetailRoute() {
  const { slug } = useParams();
  return <SpecDetail slug={slug ?? ""} />;
}

function BacktestDetailRoute() {
  const { slug } = useParams();
  return <BacktestDetail slug={slug ?? ""} />;
}

export default function App() {
  const base = normalizeBasename(import.meta.env.BASE_URL);
  const prefix = base === "/" ? "" : base;
  const isWorkspace = window.location.pathname.startsWith(prefix + "/workspace");
  return (
    <StrictMode>
      <BrowserRouter basename={normalizeBasename(import.meta.env.BASE_URL)}>
        {!isWorkspace && <Nav />}
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/workspace" element={<Shell />}>
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
        </Routes>
        {!isWorkspace && <Footer />}
      </BrowserRouter>
    </StrictMode>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
