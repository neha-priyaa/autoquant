/** The blank-screen regression: main.tsx must actually mount the app into
 * #root, not just export a component nobody renders. */
import { waitFor } from "@testing-library/react";

describe("bootstrap", () => {
  it("mounts the landing into #root on import", async () => {
    document.body.innerHTML = '<div id="root"></div>';
    await import("../src/main");
    await waitFor(() =>
      expect(document.getElementById("root")!.textContent).toContain(
        "Research the idea.",
      ),
    );
  });
});
