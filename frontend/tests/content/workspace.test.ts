import { loadWorkspace, newestRuns, type RunRow } from "../../src/content/workspace";

describe("loadWorkspace", () => {
  it.each([null, undefined, "invalid", 42])("handles invalid root %s", (raw) => {
    expect(loadWorkspace(raw).specs).toEqual([]);
  });

  it("tolerates a null spec without losing valid neighboring specs", () => {
    const workspace = loadWorkspace({ specs: [null, false, 42, "invalid", [], {},
      { slug: "valid", universe: ["SPY"] }] });
    expect(workspace.specs).toContainEqual(expect.objectContaining({ slug: "valid", universe: ["SPY"] }));
    expect(workspace.specs).not.toContain(null);
    expect(workspace.specs).toHaveLength(1);
  });

  it("preserves compatibility with scalar universes", () => {
    expect(loadWorkspace({ specs: [{ slug: "a", universe: "SPY" }] }).specs[0].universe)
      .toEqual(["SPY"]);
  });
});

describe("newestRuns", () => {
  const run = (slug: string, runAt?: string): RunRow => ({
    slug, runAt, date: "2026-10-28", lane: "article", status: "ok",
    netSharpe: null, beatsNull: null, flags: [], error: null,
  });

  it("compares timezone offsets and resolves equal instants by append order", () => {
    const runs = [run("first", "2026-10-28T10:00:00Z"),
      run("later", "2026-10-28T15:30:00+05:30"), run("older")];
    expect(newestRuns(runs).map((r) => r.slug)).toEqual(["later", "first", "older"]);
    expect(runs.map((r) => r.slug)).toEqual(["first", "later", "older"]);
  });
});

describe("loadWorkspace element validation (B2)", () => {
  it("drops triage rows that are not objects and defaults missing list fields", () => {
    const ws = loadWorkspace({ triage: [null, 42, { slug: "a", score: 3 }] });
    expect(ws.triage).toHaveLength(1);
    expect(ws.triage[0]).toMatchObject({ slug: "a", redFlags: [], missing: [] });
  });

  it("defaults catalog tags to an empty array", () => {
    const ws = loadWorkspace({ catalog: [{ id: "c1" }, null] });
    expect(ws.catalog).toHaveLength(1);
    expect(ws.catalog[0].tags).toEqual([]);
  });

  it("drops reports without a metrics array", () => {
    const ws = loadWorkspace({ reports: { bad: { text: "x" }, good: { text: "y", metrics: [] } } });
    expect(Object.keys(ws.reports)).toEqual(["good"]);
  });
});
