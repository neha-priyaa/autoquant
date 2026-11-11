import { render, screen, fireEvent } from "@testing-library/react";
import CliSnippet from "../../src/components/CliSnippet";

const COMMAND = "uv run python extract.py";

describe("CliSnippet clipboard guard", () => {
  const clipboard = Object.getOwnPropertyDescriptor(navigator, "clipboard");
  afterEach(() => {
    if (clipboard) Object.defineProperty(navigator, "clipboard", clipboard);
    else Reflect.deleteProperty(navigator, "clipboard");
    vi.restoreAllMocks();
  });

  it("copies the exact command text on success", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    render(<CliSnippet command={COMMAND} />);
    fireEvent.click(screen.getByRole("button", { name: `Copy command: ${COMMAND}` }));
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith(COMMAND));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows a failure message when writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    render(<CliSnippet command={COMMAND} />);
    fireEvent.click(screen.getByRole("button", { name: `Copy command: ${COMMAND}` }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not copy/i);
    expect(writeText).toHaveBeenCalledWith(COMMAND);
  });

  it("shows an unavailable message when clipboard is undefined", async () => {
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    render(<CliSnippet command={COMMAND} />);
    const button = screen.getByRole("button", { name: `Copy command: ${COMMAND}` });
    expect(() => fireEvent.click(button)).not.toThrow();
    expect(await screen.findByRole("status")).toHaveTextContent(/clipboard unavailable/i);
  });
});
