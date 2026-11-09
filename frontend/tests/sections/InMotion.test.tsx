import { render, screen } from "@testing-library/react";
import InMotion from "../../src/sections/InMotion";

it("renders an empty state for a chain without artifact stages", () => {
  render(<InMotion chain={{ slug: "empty", title: "Empty", stages: [] }} />);
  expect(screen.queryByRole("tab")).not.toBeInTheDocument();
  expect(screen.getByText(/No completed experiment chains yet/i)).toBeInTheDocument();
});
