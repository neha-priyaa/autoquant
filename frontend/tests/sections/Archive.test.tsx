import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import Archive from "../../src/sections/Archive";
import type { ArchiveRow } from "../../src/content/snapshot";

function SearchProbe() {
  return <output aria-label="search">{useLocation().search}</output>;
}

const rows = (): ArchiveRow[] => {
  const row = (slug: string, netSharpe: number | null): ArchiveRow => ({
    slug, netSharpe, source: "source", lane: "article", status: "ok",
    beatsNull: null, date: "2026-10-28",
  });
  return [row("missing", null), row("loss", -120), row("gain", 1)];
};

it("ranks all measured Sharpe values before missing values", async () => {
  render(<MemoryRouter><Archive rows={rows()} /></MemoryRouter>);
  await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
  const items = screen.getAllByRole("listitem");
  expect(within(items[0]).getByText("gain")).toBeInTheDocument();
  expect(within(items[1]).getByText("loss")).toBeInTheDocument();
  expect(within(items[2]).getByText("missing")).toBeInTheDocument();
});

it("initializes the sort from the URL query (#40)", () => {
  render(
    <MemoryRouter initialEntries={["/?sort=sharpe"]}>
      <Archive rows={rows()} />
    </MemoryRouter>,
  );
  expect(screen.getByRole("combobox")).toHaveValue("sharpe");
  const items = screen.getAllByRole("listitem");
  expect(within(items[0]).getByText("gain")).toBeInTheDocument();
});

it("writes the sort to the URL and removes the default (#40)", async () => {
  render(
    <MemoryRouter>
      <Archive rows={rows()} />
      <SearchProbe />
    </MemoryRouter>,
  );
  await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
  expect(screen.getByLabelText("search")).toHaveTextContent("?sort=sharpe");
  await userEvent.selectOptions(screen.getByRole("combobox"), "date");
  expect(screen.getByLabelText("search")).toHaveTextContent("");
});
