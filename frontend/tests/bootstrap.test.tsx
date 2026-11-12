/** The blank-screen regression: main.tsx must actually mount the app into
 * #root, not just export a component nobody renders. */
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

describe("bootstrap", () => {
  it("mounts the landing into #root on import", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    // index.html provides the landing title; jsdom starts empty.
    document.title = "AutoQuant — research the idea. test the evidence.";
    await act(async () => { await import("../src/main"); });
    expect(document.getElementById("root")!.textContent).toContain("Research the idea.");
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /open workspace/i }));
    // workspace screens are lazy chunks — wait for the chunk to load
    await waitFor(() => expect(screen.getByText("Research Overview")).toBeInTheDocument(), { timeout: 5000 });
    // the title effect runs after the DOM text appears, so wait for it too
    await waitFor(() => expect(document.title).toBe("Research Overview — AutoQuant"));
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
    expect(screen.queryByRole("contentinfo")).not.toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("navigation", { name: "Workspace controls" })).getByRole("link", { name: /landing/i }));
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(document.title).toBe("AutoQuant — research the idea. test the evidence.");
  }, 15000);
});
