import { loadSnapshot, emptySnapshot } from "../src/content/snapshot";

describe("loadSnapshot", () => {
  it("falls back to a valid empty snapshot when the file is missing", () => {
    const snap = loadSnapshot(undefined);
    expect(snap).toEqual(emptySnapshot());
    expect(snap.counts.articles).toBe(0);
    expect(snap.stages).toHaveLength(0);
  });

  it("accepts a parsed object with the contract shape", () => {
    const raw = { ...emptySnapshot(), generatedAt: "2026-10-20T00:00:00+00:00" };
    const snap = loadSnapshot(raw);
    expect(snap.generatedAt).toBe("2026-10-20T00:00:00+00:00");
  });

  it("coerces missing sub-objects on a partial snapshot", () => {
    const snap = loadSnapshot({ generatedAt: "x", counts: { articles: 3 } });
    expect(snap.counts).toEqual({
      articles: 3, triaged: 0, specs: 0, backtests: 0, external: 0,
    });
    expect(snap.catalog).toEqual({ series: 0, providers: [] });
  });
});
