import { render, screen, fireEvent, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Feed from "../src/ws/screens/Feed";
import Triage from "../src/ws/screens/Triage";
import Leaderboard from "../src/ws/screens/Leaderboard";
import Backtests, { BacktestDetail } from "../src/ws/screens/Backtests";
import Overview from "../src/ws/screens/Overview";
import { loadWorkspace } from "../src/content/workspace";
import type { RunRow } from "../src/content/workspace";
import { snapshot } from "../src/content/snapshot";

const W = vi.hoisted(() => ({
  articles: [
    { slug: "a1", title: "Alpha article", source: "S1", url: "https://x",
      posted: "2026-01-01", stage: "fetched", blurb: "b", triageScore: 5 },
    { slug: "a2", title: "Other piece", source: "S2", url: "https://y",
      posted: "2026-02-01", stage: "discovered", blurb: "b2", triageScore: null },
  ],
  triage: [
    { slug: "a1", title: "Alpha article", url: "https://x", claim: "claim c",
      assetClass: "equity", score: 5, redFlags: ["lookahead"], missing: [],
      reason: "r" },
    { slug: "a2", title: "Other piece", url: "https://y", claim: "weak",
      assetClass: null, score: 2, redFlags: [], missing: ["data"], reason: "" },
  ],
  specs: [{ slug: "s1", title: "S1", claim: null, universe: ["SPY"], bar: "1d",
    signal: "close > sma200", entry: "cross", exit: "cross", direction: "long_only",
    status: "PENDING", hasCode: true, raw: "meta:\n  slug: s1" }],
  runs: Array<RunRow>(
    { slug: "s1", lane: "article", status: "PENDING", netSharpe: 1.5,
      beatsNull: true, date: "2026-02-01", runAt: "2026-02-01T09:00:00Z", flags: ["WEAK: x"], error: null },
    { slug: "nb1", lane: "external", status: "error", netSharpe: null,
      beatsNull: null, date: "2026-03-01", runAt: "2026-03-01T09:00:00Z", flags: [], error: "boom" },
    { slug: "negative", lane: "article", status: "FAILED", netSharpe: -0.04,
      beatsNull: false, date: "2026-02-01", runAt: "2026-02-01T10:00:00Z", flags: [], error: null },
  ),
  reports: { s1: { metrics: [{ label: "Sharpe", strategy: "1.50", benchmark: "0.4" }],
                   text: "full report body" } },
  failed: [{ slug: "f1", error: "exit 1" }],
  catalog: [{ id: "yahoo:SPY", title: "S&P", provider: "yahoo", tags: ["etf"],
    frequency: "daily", coverageStart: "1993-01-29", license: null,
    notes: null, fallback: null }],
  catalogCount: 1,
}));

const originalRuns = [...W.runs];
afterEach(() => W.runs.splice(0, W.runs.length, ...originalRuns));

vi.mock("../src/content/workspace", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../src/content/workspace")>();
  return { ...orig, workspace: W };
});

describe("Feed", () => {
  it("searches by title", async () => {
    render(<MemoryRouter><Feed /></MemoryRouter>);
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
    expect(screen.getByText("triage 5/5")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search articles"), "alpha");
    expect(screen.queryByText("Other piece")).not.toBeInTheDocument();
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
  });
});

describe("Triage", () => {
  it("filters by minimum score", () => {
    render(<Triage />);
    expect(screen.getByLabelText("Minimum triage score")).toHaveAttribute("max", "5");
    expect(screen.getAllByText(/\/5/).length).toBe(2);
    fireEvent.change(screen.getByLabelText("Minimum triage score"), {
      target: { value: "5" },
    });
    expect(screen.getAllByText(/\/5/).length).toBe(1);
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
    expect(screen.queryByText("Other piece")).not.toBeInTheDocument();
  });
  it("distinguishes an empty filter from an empty pipeline", () => {
    const scores = W.triage.map((row) => row.score);
    W.triage.forEach((row) => { row.score = 2; });
    try {
      render(<Triage />);
      fireEvent.change(screen.getByLabelText("Minimum triage score"), { target: { value: "5" } });
      expect(screen.getByText(/No ideas match/)).toBeInTheDocument();
      expect(screen.queryByText(/Nothing triaged yet/)).not.toBeInTheDocument();
    } finally {
      W.triage.forEach((row, index) => { row.score = scores[index]; });
    }
  });
});

describe("Leaderboard", () => {
  const slugs = () => screen.getAllByRole("row").slice(1).map(
    (row) => within(row).getAllByRole("cell")[1].textContent);
  it("keeps missing measurements last in both directions", async () => {
    render(<Leaderboard />);
    expect(slugs()).toEqual(["s1", "negative", "nb1"]);
    await userEvent.click(screen.getByRole("button", { name: "Sort by netSharpe" }));
    expect(slugs()).toEqual(["negative", "s1", "nb1"]);
    await userEvent.click(screen.getByRole("button", { name: "Sort by beatsNull" }));
    expect(slugs().at(-1)).toBe("nb1");
    await userEvent.click(screen.getByRole("button", { name: "Sort by beatsNull" }));
    expect(slugs().at(-1)).toBe("nb1");
  });
  it("renders both lanes and sorts", async () => {
    render(<Leaderboard />);
    expect(screen.getByText("s1")).toBeInTheDocument();
    expect(screen.getByText("nb1")).toBeInTheDocument();
    const sortBtns = screen.getAllByRole("button", { name: /sort by/i });
    await userEvent.click(sortBtns.find((b) => b.getAttribute("aria-label") === "Sort by slug")!);
    expect(screen.getAllByText(/^(s1|nb1)$/)[0].textContent).toBe("nb1");
  });
});

describe("BacktestDetail", () => {
  it("shows the latest article run with the latest report", () => {
    W.runs.push({ ...W.runs[0], date: "2026-04-01", runAt: "2026-04-01T12:00:00Z",
      status: "FAILED", flags: ["NEW WARNING"] });
    // A newer external artifact with the same name must not replace the article run.
    W.runs.push({ ...W.runs[1], slug: "s1", date: "2026-05-01", runAt: "2026-05-01T00:00:00Z" });
    render(<BacktestDetail slug="s1" />);
    expect(screen.getByText(/article lane · 2026-04-01/)).toBeInTheDocument();
    expect(screen.getByText(/NEW WARNING/)).toBeInTheDocument();
    expect(screen.queryByText(/WEAK: x/)).not.toBeInTheDocument();
    expect(screen.getByText(/Latest report/)).toBeInTheDocument();
  });
  it("renders parsed metrics and report text", () => {
    render(<BacktestDetail slug="s1" />);
    expect(screen.getByText("1.50")).toBeInTheDocument();
    expect(screen.getByText(/full report body/)).toBeInTheDocument();
  });
  it("shows a friendly miss for unknown slugs", () => {
    render(<BacktestDetail slug="nope" />);
    expect(screen.getByText(/No backtest run found/)).toBeInTheDocument();
  });
});

describe("run ordering", () => {
  it("orders same-day runs by full timestamps", () => {
    render(<MemoryRouter><Backtests /></MemoryRouter>);
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveTextContent("negative");
    expect(links[0]).toHaveAccessibleName(/latest report/i);
    expect(links[1]).toHaveTextContent("s1");
  });
  it("orders overview runs by full timestamps too", () => {
    render(<MemoryRouter><Overview /></MemoryRouter>);
    const items = within(screen.getAllByRole("list")[1]).getAllByRole("listitem");
    expect(items[1]).toHaveTextContent("negative");
  });
});

describe("Overview stage counts", () => {
  it("shows artifact counts and leaves unknown counts unspecified", () => {
    const stages = snapshot.stages;
    snapshot.stages = stages.map((stage, index) => ({
      ...stage, count: index === 1 ? null : index === 4 ? 3 : index === 6 ? 2 : 0,
    }));
    try {
      render(<MemoryRouter><Overview /></MemoryRouter>);
      const pipeline = within(screen.getAllByRole("list")[0]);
      expect(pipeline.getByText("— — data/pages/")).toBeInTheDocument();
      expect(pipeline.getByText("3 — strategies/")).toBeInTheDocument();
      expect(pipeline.getByText("2 — reports/")).toBeInTheDocument();
    } finally {
      snapshot.stages = stages;
    }
  });
});

describe("loadWorkspace", () => {
  it("degrades to empty on garbage", () => {
    expect(loadWorkspace(null).articles).toEqual([]);
    expect(loadWorkspace(42).runs).toEqual([]);
  });
});
