import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { StatusDot } from "../src/components/StatusDot";
import { MetricReadout } from "../src/components/MetricReadout";
import Evidence from "../src/sections/Evidence";
import Archive from "../src/sections/Archive";
import { useRevealRoot } from "../src/lib/reveal";
import InMotion from "../src/sections/InMotion";
import type { ArchiveRow, Chain, Headline } from "../src/content/snapshot";

describe("StatusDot", () => {
  const dotOf = (verdict: string) => {
    const { container } = render(<StatusDot verdict={verdict} />);
    return container.querySelector("span[aria-hidden]")!;
  };
  it("maps ok-like verdicts to the accent", () => {
    expect(dotOf("ok")).toHaveClass("bg-accent");
  });
  it("maps error verdicts to fail color", () => {
    expect(dotOf("error")).toHaveClass("bg-fail");
  });
  it("maps everything else to dim", () => {
    expect(dotOf("PENDING")).toHaveClass("bg-dim");
  });
});

describe("MetricReadout", () => {
  it("renders label and value", () => {
    render(<MetricReadout label="SHARPE" value="-0.04" />);
    expect(screen.getByText("SHARPE")).toBeInTheDocument();
    expect(screen.getByText("-0.04")).toBeInTheDocument();
  });
});

const ROWS: ArchiveRow[] = [
  { slug: "s1", source: "src", lane: "article", status: "PENDING",
    netSharpe: 1.5, beatsNull: true, date: "2026-02-01" },
  { slug: "s2", source: "o/r", lane: "external", status: "ok",
    netSharpe: null, beatsNull: null, date: "2026-03-01" },
];
const CHAIN: Chain = {
  slug: "a", title: "A chain",
  stages: [
    { kind: "article", title: "a.md", body: "prose text", repoPath: "p" },
    { kind: "spec", title: "s.yaml", body: "meta: slug", repoPath: "p" },
  ],
};
const HEADLINE: Headline = {
  slug: "s1",
  metrics: [{ label: "Sharpe", strategy: "-0.04", benchmark: "0.46" }],
};

describe("Archive", () => {
  it("keeps reordered rows revealed", async () => {
    function Landing() {
      const ref = useRevealRoot();
      return <main ref={ref}><Archive rows={ROWS} /></main>;
    }
    render(<Landing />);
    expect(screen.getByText("s1").closest(".reveal")).toHaveClass("in");
    await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
    expect(screen.getByText("s1").closest(".reveal")).toHaveClass("in");
    expect(screen.getByText("s2").closest(".reveal")).toHaveClass("in");
  });

  it("orders runs on the same date by full timestamp", () => {
    render(<MemoryRouter><Archive rows={[
      { ...ROWS[0], runAt: "2026-02-01T09:00:00Z" },
      { ...ROWS[0], slug: "s2", runAt: "2026-02-01T10:00:00Z" },
    ]} /></MemoryRouter>);
    expect(screen.getAllByText(/^s[12]$/)[0]).toHaveTextContent("s2");
  });

  it("renders rows sorted by date by default", () => {
    render(<MemoryRouter><Archive rows={ROWS} /></MemoryRouter>);
    const slugs = screen.getAllByText(/s[12]/).map((e) => e.textContent);
    expect(slugs.indexOf("s2")).toBeLessThan(slugs.indexOf("s1"));
  });

  it("re-sorts by net sharpe", async () => {
    render(<MemoryRouter><Archive rows={ROWS} /></MemoryRouter>);
    await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
    const slugs = screen
      .getAllByText(/^s[12]$/)
      .map((e) => e.textContent);
    expect(slugs[0]).toBe("s1");
  });

  it("shows an empty state with no experiments", () => {
    render(<MemoryRouter><Archive rows={[]} /></MemoryRouter>);
    expect(screen.getByText(/No experiments on the leaderboard yet/i))
      .toBeInTheDocument();
  });
});

describe("Evidence", () => {
  it("renders real metrics", () => {
    render(<Evidence headline={HEADLINE} />);
    expect(screen.getByText("-0.04")).toBeInTheDocument();
    expect(screen.getByText(/LATEST RUN — s1/)).toBeInTheDocument();
  });
  it("renders the empty state without a headline", () => {
    render(<Evidence headline={null} />);
    expect(screen.getByText(/No completed backtest runs yet/i))
      .toBeInTheDocument();
  });
});

describe("InMotion", () => {
  it("switches artifact panels via tabs", async () => {
    render(<InMotion chain={CHAIN} />);
    expect(screen.getByText("prose text")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /SPEC/ }));
    expect(screen.getByText("meta: slug")).toBeInTheDocument();
  });
  it("shows an empty state with no chains", () => {
    render(<InMotion chain={null} />);
    expect(screen.getByText(/No completed experiment chains yet/i))
      .toBeInTheDocument();
  });
});
