import { renderHook, act } from "@testing-library/react";
import { useTheme, THEME_ORDER } from "../src/lib/theme";

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
    document.documentElement.dataset.theme = "light";
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
  });

  it("cycles through all four skins and persists each", () => {
    const { result } = renderHook(() => useTheme());
    for (const expected of ["light", "terminal", "amber", "dark"]) {
      act(() => result.current.toggle());
      expect(result.current.theme).toBe(expected);
      expect(document.documentElement.dataset.theme).toBe(expected);
      expect(localStorage.getItem("aq-theme")).toBe(expected);
    }
  });

  it("coerces an unknown stored theme to dark", () => {
    document.documentElement.dataset.theme = "hotdog" as never;
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });

  it("exposes the cycle order for the toggle", () => {
    expect(THEME_ORDER).toEqual(["dark", "light", "terminal", "amber"]);
  });
});
