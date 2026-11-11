import { describe, it, expect } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import TableScrollWrapper, { overflowState } from "../../src/components/TableScrollWrapper";

describe("overflowState", () => {
  it("reports no overflow when content fits", () => {
    expect(overflowState(600, 600, 0)).toEqual({ left: false, right: false });
  });

  it("reports right overflow at the start", () => {
    expect(overflowState(1200, 600, 0)).toEqual({ left: false, right: true });
  });

  it("reports both sides in the middle", () => {
    expect(overflowState(1200, 600, 300)).toEqual({ left: true, right: true });
  });

  it("reports left overflow at the end", () => {
    expect(overflowState(1200, 600, 600)).toEqual({ left: true, right: false });
  });

  it("ignores a 1px rounding difference", () => {
    expect(overflowState(601, 600, 0).right).toBe(false);
  });
});

describe("TableScrollWrapper indicator (#45)", () => {
  function scrollBox(container: HTMLElement, width: { scroll: number; client: number }) {
    const box = container.querySelector<HTMLElement>(".overflow-x-auto");
    if (!box) throw new Error("scroll container missing");
    Object.defineProperty(box, "scrollWidth", { configurable: true, value: width.scroll });
    Object.defineProperty(box, "clientWidth", { configurable: true, value: width.client });
    return box;
  }

  it("shows the scroll cue while columns continue off-screen", () => {
    const { container } = render(
      <TableScrollWrapper><table><tbody><tr><td>x</td></tr></tbody></table></TableScrollWrapper>,
    );
    scrollBox(container, { scroll: 1200, client: 600 });
    fireEvent.scroll(container.querySelector(".overflow-x-auto")!);
    expect(screen.getByText("scroll →")).toBeInTheDocument();
  });

  it("hides the cue once scrolled to the right edge", () => {
    const { container } = render(
      <TableScrollWrapper><table><tbody><tr><td>x</td></tr></tbody></table></TableScrollWrapper>,
    );
    const box = scrollBox(container, { scroll: 1200, client: 600 });
    fireEvent.scroll(box);
    box.scrollLeft = 600;
    fireEvent.scroll(box);
    expect(screen.queryByText("scroll →")).not.toBeInTheDocument();
  });
});
