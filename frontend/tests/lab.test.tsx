import { render, screen } from "@testing-library/react";
import { SpecDetail } from "../src/ws/screens/Lab";
import { workspace } from "../src/content/workspace";

vi.mock("../src/content/workspace", () => ({
  workspace: {
    specs: [{ slug: "example", universe: ["SPY"], hasCode: false, raw: "meta:\n  slug: example" }],
    runs: [],
  },
}));

const spec = workspace.specs[0];
afterEach(() => {
  spec.raw = "meta:\n  slug: example";
  delete spec.rawTruncated;
});

it("offers copy for a complete specification", () => {
  render(<SpecDetail slug="example" />);
  expect(screen.getByRole("button", { name: "Copy spec YAML" })).toBeInTheDocument();
});

it("labels legacy truncated YAML and does not offer it as a complete copy", () => {
  spec.raw = "meta: …";
  render(<SpecDetail slug="example" />);
  expect(screen.getByText(/preview is truncated/i)).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Copy spec YAML" })).not.toBeInTheDocument();
});

it("honors an explicit completeness marker for YAML ending with an ellipsis", () => {
  spec.raw = "# Intentional ellipsis …";
  spec.rawTruncated = false;
  render(<SpecDetail slug="example" />);
  expect(screen.getByRole("button", { name: "Copy spec YAML" })).toBeInTheDocument();
});
