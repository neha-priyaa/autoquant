import { sendChat } from "../src/lib/chatClient";

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
