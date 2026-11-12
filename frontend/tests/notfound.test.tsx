import { act, screen } from "@testing-library/react";
import { vi } from "vitest";

describe("notfound", () => {
  it("renders 404 with a home link for an unmapped root path", async () => {
    window.history.pushState({}, "", "/notfound");
    document.body.innerHTML = '<div id="root"></div>';
    await act(async () => {
      await import("../src/main");
    });
    expect(
      screen.getByRole("heading", { level: 1 }),
    ).toHaveTextContent("This page doesn't exist.");
    expect(screen.getByRole("link", { name: /home/i })).toHaveAttribute(
      "href",
      "/",
    );
  });

  it("shows one main landmark for an unmapped workspace path", async () => {
    vi.resetModules();
    window.history.pushState({}, "", "/workspace/unknown");
    document.body.innerHTML = '<div id="root"></div>';
    await act(async () => {
      await import("../src/main");
    });
    expect(await screen.findByText("This page doesn't exist.")).toBeInTheDocument();
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });
});
