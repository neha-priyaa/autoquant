import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "./styles/tokens.css";
import Nav from "./components/Nav";
import Footer from "./components/Footer";
import Hero from "./sections/Hero";
import Pipeline from "./sections/Pipeline";
import InMotion from "./sections/InMotion";
import Evidence from "./sections/Evidence";
import Archive from "./sections/Archive";
import FinalCta from "./sections/FinalCta";
import WorkspaceStub from "./sections/WorkspaceStub";
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

export default function App() {
  return (
    <StrictMode>
      <BrowserRouter basename={normalizeBasename(import.meta.env.BASE_URL)}>
        <Nav />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/workspace" element={<WorkspaceStub />} />
        </Routes>
        <Footer />
      </BrowserRouter>
    </StrictMode>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
