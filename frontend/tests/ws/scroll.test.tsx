import { render, renderHook } from "@testing-library/react";
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
});


import { useDocumentTitle } from "../../src/lib/useDocumentTitle";

describe("#44 dynamic document titles", () => {
  it("sets the tab title and restores the default when cleared", () => {
    function Probe({ title }: { title: string | null }) {
      useDocumentTitle(title);
      return null;
    }
    const { rerender } = renderHook(
      ({ title }: { title: string | null }) => useDocumentTitle(title),
      { initialProps: { title: "Leaderboard" as string | null } },
    );
    expect(document.title).toBe("Leaderboard — AutoQuant");
    rerender({ title: null });
    expect(document.title).toBe("AutoQuant — research the idea. test the evidence.");
  });
});
