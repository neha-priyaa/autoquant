/** The blank-screen regression: main.tsx must actually mount the app into
 * #root, not just export a component nobody renders. */
import { act, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("bootstrap", () => {
  it("mounts the landing into #root on import", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    await act(async () => { await import("../src/main"); });
    expect(document.getElementById("root")!.textContent).toContain("Research the idea.");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /open workspace/i }));
    expect(screen.getByText("Research Overview")).toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /landing/i }));
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
  }, 15000);
});
