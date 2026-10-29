import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Chat from "../src/ws/screens/Chat";
import { sendChat } from "../src/lib/chatClient";

vi.mock("../src/lib/chatClient", () => ({ sendChat: vi.fn() }));

describe("Chat screen", () => {
  it("shows the offline note when the bridge fails", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: false, offline: true,
      error: "The local bridge isn't reachable.",
    });
    render(<Chat />);
    await userEvent.type(screen.getByLabelText("Message"), "hi");
    await userEvent.click(screen.getByLabelText("Send message"));
    await waitFor(() =>
      expect(screen.getByText(/local bridge isn't reachable/)).toBeInTheDocument());
  });

  it("renders the reply as an assistant bubble", async () => {
    vi.mocked(sendChat).mockResolvedValue({
      ok: true, reply: "7 backtests", sessionId: "s1",
    });
    render(<Chat />);
    await userEvent.type(screen.getByLabelText("Message"), "how many runs?");
    await userEvent.click(screen.getByLabelText("Send message"));
    await waitFor(() => expect(screen.getByText("7 backtests")).toBeInTheDocument());
  });
});
