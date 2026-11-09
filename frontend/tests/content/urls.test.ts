import { httpUrl } from "../../src/content/urls";

it.each([null, 42, "", "/local", "//example.com", "javascript:alert(1)",
  "JaVaScRiPt:alert(1)", "java\nscript:alert(1)", "data:text/html,hello", "file:///tmp/private"])(
  "rejects unsafe or invalid external URLs: %s", (value) => {
    expect(httpUrl(value)).toBeUndefined();
  },
);

it.each(["https://example.com/article", "http://example.com/article"])(
  "preserves safe source URLs: %s", (value) => {
    expect(httpUrl(value)).toBe(value);
  },
);
