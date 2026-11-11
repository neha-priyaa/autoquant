import { renderHook } from "@testing-library/react";
import { useDocumentTitle } from "../../src/lib/useDocumentTitle";

describe("useDocumentTitle (#44)", () => {
  it("sets the tab title with the brand suffix", () => {
    renderHook(() => useDocumentTitle("Leaderboard"));
    expect(document.title).toBe("Leaderboard — AutoQuant");
  });

  it("restores the default brand title when cleared", () => {
    const { rerender } = renderHook(
      ({ title }: { title: string | null }) => useDocumentTitle(title),
      { initialProps: { title: "Leaderboard" as string | null } },
    );
    rerender({ title: null });
    expect(document.title).toBe("AutoQuant — research the idea. test the evidence.");
  });

  it("restores the previous title on unmount", () => {
    document.title = "before";
    const { unmount } = renderHook(() => useDocumentTitle("Leaderboard"));
    unmount();
    expect(document.title).toBe("before");
  });
});
