import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import Shell from "../src/ws/Shell";

it("provides landing navigation and persistent theme controls in the mobile toolbar", () => {
  document.documentElement.dataset.theme = "dark";
  render(
    <MemoryRouter initialEntries={["/workspace"]}>
      <Routes>
        <Route path="/" element={<p>Landing page</p>} />
        <Route path="/workspace" element={<Shell />}>
          <Route index element={<p>Workspace page</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
  const controls = within(screen.getByRole("navigation", { name: "Workspace controls" }));
  fireEvent.click(controls.getByRole("button", { name: "Switch to light mode" }));
  expect(document.documentElement.dataset.theme).toBe("light");
  fireEvent.click(controls.getByRole("button", { name: /Cycle skin/ }));
  expect(document.documentElement.dataset.theme).toBe("ivory");
  expect(localStorage.getItem("aq-theme")).toBe("ivory");
  fireEvent.click(controls.getByRole("link", { name: /Landing/ }));
  expect(screen.getByText("Landing page")).toBeInTheDocument();
});
