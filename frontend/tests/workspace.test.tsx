import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Feed from "../src/ws/screens/Feed";
import Triage from "../src/ws/screens/Triage";
import Leaderboard from "../src/ws/screens/Leaderboard";
import { BacktestDetail } from "../src/ws/screens/Backtests";
import { loadWorkspace } from "../src/content/workspace";

const W = vi.hoisted(() => ({
  articles: [
    { slug: "a1", title: "Alpha article", source: "S1", url: "https://x",
      posted: "2026-01-01", stage: "fetched", blurb: "b", triageScore: 7 },
    { slug: "a2", title: "Other piece", source: "S2", url: "https://y",
      posted: "2026-02-01", stage: "discovered", blurb: "b2", triageScore: null },
  ],
  triage: [
    { slug: "a1", title: "Alpha article", url: "https://x", claim: "claim c",
      assetClass: "equity", score: 7, redFlags: ["lookahead"], missing: [],
      reason: "r" },
    { slug: "a2", title: "Other piece", url: "https://y", claim: "weak",
      assetClass: null, score: 2, redFlags: [], missing: ["data"], reason: "" },
  ],
  specs: [{ slug: "s1", title: "S1", claim: null, universe: ["SPY"], bar: "1d",
    signal: "close > sma200", entry: "cross", exit: "cross", direction: "long_only",
    status: "PENDING", hasCode: true, raw: "meta:\n  slug: s1" }],
  runs: [
    { slug: "s1", lane: "article", status: "PENDING", netSharpe: 1.5,
      beatsNull: true, date: "2026-02-01", flags: ["WEAK: x"], error: null },
    { slug: "nb1", lane: "external", status: "error", netSharpe: null,
      beatsNull: null, date: "2026-03-01", flags: [], error: "boom" },
  ],
  reports: { s1: { metrics: [{ label: "Sharpe", strategy: "1.50", benchmark: "0.4" }],
                   text: "full report body" } },
  failed: [{ slug: "f1", error: "exit 1" }],
  catalog: [{ id: "yahoo:SPY", title: "S&P", provider: "yahoo", tags: ["etf"],
    frequency: "daily", coverageStart: "1993-01-29", license: null,
    notes: null, fallback: null }],
  catalogCount: 1,
}));

vi.mock("../src/content/workspace", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../src/content/workspace")>();
  return { ...orig, workspace: W };
});

describe("Feed", () => {
  it("searches by title", async () => {
    render(<MemoryRouter><Feed /></MemoryRouter>);
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search articles"), "alpha");
    expect(screen.queryByText("Other piece")).not.toBeInTheDocument();
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
  });
});

describe("Triage", () => {
  it("filters by minimum score", () => {
    render(<Triage />);
    expect(screen.getAllByText(/\/10/).length).toBe(2);
    fireEvent.change(screen.getByLabelText("Minimum triage score"), {
      target: { value: "5" },
    });
    expect(screen.getAllByText(/\/10/).length).toBe(1);
    expect(screen.getByText("Alpha article")).toBeInTheDocument();
    expect(screen.queryByText("Other piece")).not.toBeInTheDocument();
  });
});

describe("Leaderboard", () => {
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

describe("loadWorkspace", () => {
  it("degrades to empty on garbage", () => {
    expect(loadWorkspace(null).articles).toEqual([]);
    expect(loadWorkspace(42).runs).toEqual([]);
  });
});
