import { exportToCsv, exportToJson } from "../src/lib/export";

const clicks: HTMLAnchorElement[] = [];
const created: { blob: Blob; url: string }[] = [];

beforeAll(() => {
  vi.stubGlobal("Blob", class {
    content: string;
    constructor(parts: BlobPart[]) {
      this.content = parts.map((p) => String(p)).join("");
    }
    text() { return Promise.resolve(this.content); }
  });
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: (b: Blob) => {
      const url = `blob:mock-${created.length}`;
      created.push({ blob: b, url });
      return url;
    },
    revokeObjectURL: vi.fn(),
  });
  vi.stubGlobal("document", {
    ...document,
    createElement: () => {
      const a = { href: "", download: "", click: () => clicks.push(a as unknown as HTMLAnchorElement) };
      return a;
    },
  });
});
afterEach(() => { clicks.length = 0; created.length = 0; });

describe("exportToCsv", () => {
  it("writes headers + rows as csv", async () => {
    exportToCsv("lb", ["name", "sharpe"], [["a", 1.5]]);
    const text = await created[0].blob.text();
    expect(text).toBe("name,sharpe\na,1.5");
    expect(clicks[0].download).toBe("lb.csv");
  });

  it("escapes commas, quotes and newlines", async () => {
    exportToCsv("x", ["v"], [['a,b "q"', 1]]);
    const text = await created[0].blob.text();
    expect(text).toBe('v\n"a,b ""q""",1');
  });

  it("renders null/undefined as empty cells", async () => {
    exportToCsv("x", ["a", "b"], [[null, undefined]]);
    expect(await created[0].blob.text()).toBe("a,b\n,");
  });
});

describe("exportToJson", () => {
  it("downloads pretty-printed json", async () => {
    exportToJson("data", { runs: [1, 2] });
    const text = await created[0].blob.text();
    expect(JSON.parse(text)).toEqual({ runs: [1, 2] });
    expect(clicks[0].download).toBe("data.json");
  });
});

describe("CSV injection & \\r hardening (#48)", () => {
  it("quotes values containing \\r so a record never splits", async () => {
    exportToCsv("x", ["v"], [["line1\rline2"]]);
    const text = await created[0].blob.text();
    expect(text).toBe('v\n"line1\rline2"');
    expect(text.split("\r").length - 1).toBe(1);
  });

  it.each(["=1+1", "+2", "@cmd", "-2"])(
    "neutralises formula-leading value %s", async (v) => {
      exportToCsv("x", ["v"], [[v]]);
      const text = await created[0].blob.text();
      expect(text).toBe(`v\n'${v}`);
    });
});
