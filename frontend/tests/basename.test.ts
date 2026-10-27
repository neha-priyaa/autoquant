import { normalizeBasename } from "../src/lib/basename";

describe("normalizeBasename", () => {
  it("keeps root base as /", () => {
    expect(normalizeBasename("/")).toBe("/");
  });
  it("strips the trailing slash from a subpath base", () => {
    expect(normalizeBasename("/autoquant/")).toBe("/autoquant");
  });
});
