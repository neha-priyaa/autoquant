import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BacktestDetail } from "../../../src/ws/screens/Backtests";

describe("BacktestDetail with inherited Object.prototype names (B1)", () => {
  it.each(["constructor", "__proto__", "toString"])("renders a not-found message for %s", (slug) => {
    const { container } = render(<MemoryRouter><BacktestDetail slug={slug} /></MemoryRouter>);
    expect(container.textContent).toContain(`No backtest run found for ${slug}.`);
  });
});
