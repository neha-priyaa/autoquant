import { renderHook, act } from "@testing-library/react";
import { useTheme } from "../src/lib/theme";

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

  it("toggle flips the theme and persists it", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.toggle());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("aq-theme")).toBe("light");
    act(() => result.current.toggle());
    expect(localStorage.getItem("aq-theme")).toBe("dark");
  });
});
