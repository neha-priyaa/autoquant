import { overflowState } from "../src/components/TableScrollWrapper";

describe("overflowState", () => {
  it("no indicators when content fits", () => {
    expect(overflowState(600, 600, 0)).toEqual({ left: false, right: false });
  });
  it("right indicator at the start of a scrollable table", () => {
    expect(overflowState(1200, 600, 0)).toEqual({ left: false, right: true });
  });
  it("both indicators mid-scroll", () => {
    expect(overflowState(1200, 600, 300)).toEqual({ left: true, right: true });
  });
  it("left indicator at the end", () => {
    expect(overflowState(1200, 600, 600)).toEqual({ left: true, right: false });
  });
  it("1px rounding slop does not flicker indicators", () => {
    expect(overflowState(601, 600, 0).right).toBe(false);
  });
});
