import { exportToCsv, exportToJson } from "../../src/lib/export";

let blobs: string[] = [];
let clicked: HTMLAnchorElement[] = [];
let revoke = vi.fn((_url: string) => undefined);

beforeEach(() => {
  vi.useFakeTimers();
  blobs = [];
  clicked = [];
  vi.stubGlobal("Blob", class {
    content: string;
    constructor(parts: BlobPart[]) {
      this.content = parts.map((p) => String(p)).join("");
      blobs.push(this.content);
    }
  });
  URL.createObjectURL = vi.fn(() => "blob:mock");
  revoke = vi.fn((_url: string) => undefined);
  URL.revokeObjectURL = revoke;
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    clicked.push(this);
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("exportToCsv", () => {
  it("writes headers + rows as csv and downloads it", () => {
    exportToCsv("lb", ["name", "sharpe"], [["a", 1.5]]);
    expect(blobs[0]).toBe("name,sharpe\na,1.5");
    expect(clicked[0].download).toBe("lb.csv");
  });

  it("escapes commas, quotes and newlines", () => {
    exportToCsv("x", ["v"], [['a,b "q"', 1]]);
    expect(blobs[0]).toBe('v\n"a,b ""q""",1');
  });

  it("renders null/undefined as empty cells", () => {
    exportToCsv("x", ["a", "b"], [[null, undefined]]);
    expect(blobs[0]).toBe("a,b\n,");
  });

  it("quotes values containing \\r so a record never splits (#48)", () => {
    exportToCsv("x", ["v"], [["line1\rline2"]]);
    expect(blobs[0]).toBe('v\n"line1\rline2"');
  });

  it.each(["=1+1", "+2", "@cmd", "-2"])(
    "neutralises formula-leading value %s (#48)", (v) => {
      exportToCsv("x", ["v"], [[v]]);
      expect(blobs[0]).toBe(`v\n'${v}`);
    });
});

describe("exportToJson", () => {
  it("downloads pretty-printed json", () => {
    exportToJson("data", { runs: [1, 2] });
    expect(JSON.parse(blobs[0])).toEqual({ runs: [1, 2] });
    expect(clicked[0].download).toBe("data.json");
  });
});

describe("download lifecycle", () => {
  it("keeps the object URL alive until after the click has been dispatched", () => {
    exportToJson("data", {});
    expect(revoke).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revoke).toHaveBeenCalledWith("blob:mock");
  });

  it("does not leave the anchor attached to the document", () => {
    exportToJson("data", {});
    expect(clicked[0].isConnected).toBe(false);
  });
});
