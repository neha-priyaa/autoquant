import { listChats, loadChat, sendChat } from "../src/lib/chatClient";

describe("sendChat", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts to the bridge and unwraps the reply", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ reply: "PONG", sessionId: "abc" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const out = await sendChat("hi", null);
    expect(out).toEqual({ ok: true, reply: "PONG", sessionId: "abc" });
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8787/api/chat");
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      message: "hi", sessionId: null,
    });
  });

  it("flags offline when the bridge is unreachable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    const out = await sendChat("hi", null);
    expect(out).toMatchObject({ ok: false, offline: true });
  });

  it("surfaces bridge errors without the offline flag", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.resolve({ error: "boom from cli" }),
    }));
    const out = await sendChat("hi", "abc");
    expect(out).toMatchObject({ ok: false, offline: false, error: "boom from cli" });
  });
});

describe("listChats", () => {
  afterEach(() => vi.unstubAllGlobals());

  const reply = (body: unknown) =>
    vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(body) });

  it("returns saved conversations with missing fields defaulted", async () => {
    vi.stubGlobal("fetch", reply([
      { sessionId: "a", title: "runs?", updated: "2026-01-02", messageCount: 4 },
      { sessionId: "b" },
    ]));
    expect(await listChats()).toEqual([
      { sessionId: "a", title: "runs?", updated: "2026-01-02", messageCount: 4 },
      { sessionId: "b", title: "Untitled", updated: null, messageCount: 0 },
    ]);
  });

  it("drops entries without a session id", async () => {
    vi.stubGlobal("fetch", reply([
      null, "junk", { title: "no id" }, { sessionId: 7 }, { sessionId: "ok" },
    ]));
    expect(await listChats()).toEqual([
      { sessionId: "ok", title: "Untitled", updated: null, messageCount: 0 },
    ]);
  });

  it("returns nothing when the payload is not a list", async () => {
    vi.stubGlobal("fetch", reply({ chats: [] }));
    expect(await listChats()).toEqual([]);
  });

  it("returns nothing when the bridge is offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    expect(await listChats()).toEqual([]);
  });
});

describe("loadChat", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns the transcript turns", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        sessionId: "a",
        messages: [
          { role: "user", text: "hi" },
          { role: "assistant", text: "PONG" },
        ],
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    expect(await loadChat("a")).toEqual([
      { role: "user", text: "hi" },
      { role: "assistant", text: "PONG" },
    ]);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "http://127.0.0.1:8787/api/chats/a");
  });

  it("drops malformed turns", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        messages: [
          null, { role: "system", text: "x" }, { role: "user" },
          { role: "user", text: 5 }, { role: "user", text: "kept" },
        ],
      }),
    }));
    expect(await loadChat("a")).toEqual([{ role: "user", text: "kept" }]);
  });

  it("returns nothing for an unknown or offline chat", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    expect(await loadChat("gone")).toEqual([]);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    expect(await loadChat("gone")).toEqual([]);
  });
});
