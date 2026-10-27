import { renderHook, act } from "@testing-library/react";
import { useTheme, THEMES, THEME_ORDER } from "../src/lib/theme";

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.removeItem("aq-theme");
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to dark when nothing is set", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("starts from the pre-paint data-theme when present", () => {
    document.documentElement.dataset.theme = "zenburn";
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("zenburn");
  });

  it("cycles skins within the current mode", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.cycleTheme()); // dark -> terminal
    expect(result.current.theme).toBe("terminal");
    expect(THEMES.terminal.mode).toBe("dark");
    act(() => result.current.cycleTheme()); // terminal -> amber
    expect(result.current.theme).toBe("amber");
    // never leaves the mode while cycling
    act(() => result.current.cycleTheme());
    act(() => result.current.cycleTheme());
    act(() => result.current.cycleTheme());
    act(() => result.current.cycleTheme());
    expect(THEMES[result.current.theme].mode).toBe("dark");
  });

  it("mode toggle keeps the family when it exists in both modes", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.cycleTheme()); // dark -> terminal (family terminal, dark-only)
    act(() => result.current.setMode("light"));
    expect(result.current.theme).toBe("light"); // dark-only family falls back to default light
    act(() => result.current.setMode("dark"));
    expect(result.current.theme).toBe("dark");
  });

  it("mode toggle on the colorblind family flips cb-dark <-> cb-light", () => {
    document.documentElement.dataset.theme = "cb-dark";
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setMode("light"));
    expect(result.current.theme).toBe("cb-light");
    act(() => result.current.setMode("dark"));
    expect(result.current.theme).toBe("cb-dark");
  });

  it("coerces an unknown stored theme to dark", () => {
    document.documentElement.dataset.theme = "hotdog" as never;
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("exposes every theme with a mode and family", () => {
    for (const t of THEME_ORDER) {
      expect(["dark", "light"]).toContain(THEMES[t].mode);
      expect(THEMES[t].family).toBeTruthy();
    }
  });
});
