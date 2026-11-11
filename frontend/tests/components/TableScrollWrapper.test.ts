import { describe, it, expect } from "vitest";
import { overflowState } from "../../src/components/TableScrollWrapper";

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
