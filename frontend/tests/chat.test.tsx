import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Chat from "../src/ws/screens/Chat";
import { listChats, loadChat, sendChat } from "../src/lib/chatClient";

vi.mock("../src/lib/chatClient", () => ({
  sendChat: vi.fn(),
  listChats: vi.fn(),
  loadChat: vi.fn(),
}));

const savedChat = (sessionId: string, title: string) => ({
  sessionId, title, updated: "2026-01-02T10:00:00+00:00", messageCount: 2,
});

async function ask(text: string) {
  await userEvent.type(screen.getByLabelText("Message"), text);
  await userEvent.click(screen.getByLabelText("Send message"));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listChats).mockResolvedValue([]);
  vi.mocked(loadChat).mockResolvedValue([]);
});

describe("Chat screen", () => {
  it("shows the offline note when the bridge fails", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: false, offline: true,
      error: "The local bridge isn't reachable.",
    });
    render(<Chat />);
    await ask("hi");
    await waitFor(() =>
      expect(screen.getByText(/local bridge isn't reachable/)).toBeInTheDocument());
  });

  it("renders the reply as an assistant bubble", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: true, reply: "7 backtests", sessionId: "s1",
    });
    render(<Chat />);
    await ask("how many runs?");
    await waitFor(() => expect(screen.getByText("7 backtests")).toBeInTheDocument());
  });

  it("renders markdown in the reply — bold, lists, tables", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: true,
      reply: "Best is **spy-200dma**:\n\n- sharpe **1.06**\n\n| run | state |\n|---|---|\n| a | error |",
      sessionId: "s1",
    });
    render(<Chat />);
    await ask("best run?");
    await waitFor(() => {
      const strongs = [...document.querySelectorAll(".md strong")].map(s => s.textContent);
      expect(strongs).toContain("1.06");
      expect(document.querySelector(".md li")?.textContent).toContain("1.06");
      expect(document.querySelector(".md table")).not.toBeNull();
    });
  });
});

describe("Chat history", () => {
  it("restores the most recent saved conversation on load", async () => {
    vi.mocked(listChats).mockResolvedValue([
      savedChat("b", "sharpe leaderboard?"),
      savedChat("a", "how many runs?"),
    ]);
    vi.mocked(loadChat).mockResolvedValue([
      { role: "user", text: "how many runs?" },
      { role: "assistant", text: "7 backtests" },
    ]);
    render(<Chat />);
    await waitFor(() =>
      expect(screen.getByText("7 backtests")).toBeInTheDocument());
    expect(screen.getByText("how many runs?")).toBeInTheDocument();
    expect(loadChat).toHaveBeenCalledWith("b");
  });

  it("continues the restored conversation instead of starting over", async () => {
    vi.mocked(listChats).mockResolvedValue([savedChat("b", "runs?")]);
    vi.mocked(loadChat).mockResolvedValue([
      { role: "user", text: "runs?" },
      { role: "assistant", text: "7" },
    ]);
    vi.mocked(sendChat).mockResolvedValue({
      ok: true, reply: "8", sessionId: "b",
    });
    render(<Chat />);
    await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
    await ask("and now?");
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith("and now?", "b"));
  });

  it("lists saved conversations and opens one", async () => {
    vi.mocked(listChats).mockResolvedValue([
      savedChat("b", "newest question"),
      savedChat("a", "older question"),
    ]);
    vi.mocked(loadChat).mockImplementation(async (id) =>
      id === "a"
        ? [{ role: "user", text: "older question" },
           { role: "assistant", text: "older answer" }]
        : [{ role: "user", text: "newest question" },
           { role: "assistant", text: "newest answer" }]);
    render(<Chat />);
    await waitFor(() =>
      expect(screen.getByText("newest answer")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /HISTORY \(2\)/ }));
    await userEvent.click(screen.getByText("older question"));
    await waitFor(() =>
      expect(screen.getByText("older answer")).toBeInTheDocument());
    expect(screen.queryByText("newest answer")).not.toBeInTheDocument();
  });

  it("starts a fresh conversation after NEW CHAT", async () => {
    vi.mocked(listChats).mockResolvedValue([savedChat("b", "runs?")]);
    vi.mocked(loadChat).mockResolvedValue([
      { role: "user", text: "runs?" },
      { role: "assistant", text: "7" },
    ]);
    vi.mocked(sendChat).mockResolvedValue({
      ok: true, reply: "fresh", sessionId: "c",
    });
    render(<Chat />);
    await waitFor(() => expect(screen.getByText("7")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "NEW CHAT" }));
    expect(screen.queryByText("7")).not.toBeInTheDocument();
    await ask("first question");
    await waitFor(() =>
      expect(sendChat).toHaveBeenCalledWith("first question", null));
  });

  it("refreshes the saved list after an answer", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: true, reply: "PONG", sessionId: "s1",
    });
    render(<Chat />);
    await waitFor(() => expect(listChats).toHaveBeenCalledTimes(1));
    await ask("hi");
    await waitFor(() => expect(listChats).toHaveBeenCalledTimes(2));
  });

  it("says so when nothing has been saved yet", async () => {
    render(<Chat />);
    await waitFor(() => expect(listChats).toHaveBeenCalled());
    await userEvent.click(screen.getByRole("button", { name: /HISTORY \(0\)/ }));
    expect(screen.getByText(/No saved conversations yet/)).toBeInTheDocument();
  });
});
