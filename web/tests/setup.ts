import "@testing-library/jest-dom";

// Node 25 exposes a global `localStorage` (experimental) that can shadow
// jsdom's working implementation without implementing its methods. Provide
// a minimal in-memory storage only when the real one is unusable.
if (typeof localStorage?.getItem !== "function" ||
    typeof localStorage?.setItem !== "function" ||
    typeof localStorage?.removeItem !== "function") {
  const store = new Map<string, string>();
  Object.defineProperty(globalThis, "localStorage", {
    value: {
      getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
      setItem: (k: string, v: string) => { store.set(k, String(v)); },
      removeItem: (k: string) => { store.delete(k); },
      clear: () => store.clear(),
    },
    configurable: true,
  });
}
