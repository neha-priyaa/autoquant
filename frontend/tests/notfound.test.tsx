import { act, screen } from "@testing-library/react";

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
});
