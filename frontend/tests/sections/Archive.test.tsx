import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Archive from "../../src/sections/Archive";
import type { ArchiveRow } from "../../src/content/snapshot";

it("ranks all measured Sharpe values before missing values", async () => {
  const row = (slug: string, netSharpe: number | null): ArchiveRow => ({
    slug, netSharpe, source: "source", lane: "article", status: "ok",
    beatsNull: null, date: "2026-10-28",
  });
  render(<Archive rows={[row("missing", null), row("loss", -120), row("gain", 1)]} />);
  await userEvent.selectOptions(screen.getByRole("combobox"), "sharpe");
  const rows = screen.getAllByRole("listitem");
  expect(within(rows[0]).getByText("gain")).toBeInTheDocument();
  expect(within(rows[1]).getByText("loss")).toBeInTheDocument();
  expect(within(rows[2]).getByText("missing")).toBeInTheDocument();
});
