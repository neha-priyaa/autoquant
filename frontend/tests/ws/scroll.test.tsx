import { render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BacktestDetail } from "../../src/ws/screens/Backtests";
import { workspace } from "../../src/content/workspace";

vi.mock("../../src/content/workspace", async (importOriginal) => {
  const orig = await importOriginal<typeof import("../../src/content/workspace")>();
  return { ...orig, workspace: { ...orig.workspace, reports: { s1: { metrics: [], text: "long report" } } } };
});

describe("#43 keyboard-scrollable previews", () => {
  it("report pre is focusable", () => {
    render(<MemoryRouter><BacktestDetail slug="s1" /></MemoryRouter>);
    const pre = document.querySelector("pre[tabindex='0']");
    expect(pre).not.toBeNull();
    expect(pre?.className).toContain("overflow-auto");
    expect(workspace.reports.s1?.text).toBe("long report");
  });

  it("labels the report preview as a region", () => {
    render(<MemoryRouter><BacktestDetail slug="s1" /></MemoryRouter>);
    const pre = screen.getByRole("region", { name: "Backtest report preview" });
    expect(pre).toHaveAttribute("tabindex", "0");
  });
});

describe("#45 table scroll affordance", () => {
  it("wraps the report metrics table", () => {
    render(<MemoryRouter><BacktestDetail slug="s1" /></MemoryRouter>);
    const table = document.querySelector("table");
    expect(table?.closest(".overflow-x-auto")).not.toBeNull();
  });
});


import { useDocumentTitle } from "../../src/lib/useDocumentTitle";

describe("#44 dynamic document titles", () => {
  it("sets the tab title and restores the default when cleared", () => {
    const { rerender } = renderHook(
      ({ title }: { title: string | null }) => useDocumentTitle(title),
      { initialProps: { title: "Leaderboard" as string | null } },
    );
    expect(document.title).toBe("Leaderboard — AutoQuant");
    rerender({ title: null });
    expect(document.title).toBe("AutoQuant — research the idea. test the evidence.");
  });

  it("restores the previous title on unmount", () => {
    document.title = "before";
    const { unmount } = renderHook(() => useDocumentTitle("Leaderboard"));
    expect(document.title).toBe("Leaderboard — AutoQuant");
    unmount();
    expect(document.title).toBe("before");
  });
});
