import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Article } from "../../../src/content/workspace";
import Feed from "../../../src/ws/screens/Feed";

const { articles } = vi.hoisted(() => ({ articles: [] as Article[] }));
vi.mock("../../../src/content/workspace", () => ({ workspace: { articles } }));

const article = (title: string, stage: string, slug: string | null): Article => ({
  title, stage, slug, url: `https://example.com/${title}`, source: "source",
  posted: null, blurb: `${title} details`, triageScore: null,
});

beforeEach(() => { articles.length = 0; });

it.each(["javascript:alert(1)", "data:text/html,<h1>untrusted</h1>"])(
  "does not publish an unsafe source URL: %s", async (url) => {
    articles.push({ ...article("Unsafe article", "fetched", "unsafe"), url });
    render(<Feed />);
    await userEvent.click(screen.getByRole("button", { name: /Unsafe article/ }));
    expect(screen.queryByRole("link", { name: /read the source article/i }))
      .not.toBeInTheDocument();
  },
);

it("renders imported markup as text without creating executable elements", async () => {
  const markup = '<img src=x onerror="alert(1)">';
  articles.push({ ...article("Markup article", "fetched", "markup"), blurb: markup });
  const { container } = render(<Feed />);
  await userEvent.click(screen.getByRole("button", { name: /Markup article/ }));
  expect(screen.getByText(markup)).toBeInTheDocument();
  expect(container.querySelector("img")).toBeNull();
});

it("opens and closes only the selected article when slugs are absent", async () => {
  articles.push(article("First", "discovered", null), article("Second", "discovered", null));
  render(<Feed />);
  expect(screen.queryAllByRole("link", { name: /read the source article/i })).toHaveLength(0);
  const toggle = screen.getByRole("button", { name: /First/ });
  toggle.focus();
  await userEvent.keyboard("{Enter}");
  expect(toggle).toHaveAttribute("aria-expanded", "true");
  expect(screen.getAllByRole("link", { name: /read the source article/i })).toHaveLength(1);
  expect(screen.getByText("First details")).toBeInTheDocument();
  expect(screen.queryByText("Second details")).not.toBeInTheDocument();
  await userEvent.keyboard(" ");
  expect(toggle).toHaveAttribute("aria-expanded", "false");
  expect(screen.queryByText("First details")).not.toBeInTheDocument();
});

it("combines stage and text filters and restores rows when filters clear", async () => {
  articles.push(article("First", "fetched", "first"), article("Second", "triaged", "second"));
  render(<Feed />);
  await userEvent.click(screen.getByRole("button", { name: "TRIAGED" }));
  expect(screen.queryByRole("heading", { name: "First" })).not.toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Search articles" }), "second");
  expect(screen.getByRole("heading", { name: "Second" })).toBeInTheDocument();
  await userEvent.type(screen.getByRole("textbox", { name: "Search articles" }), " unknown");
  expect(screen.queryByRole("heading", { level: 2 })).not.toBeInTheDocument();
  expect(screen.getByText(/No articles match/)).toBeInTheDocument();
  await userEvent.clear(screen.getByRole("textbox", { name: "Search articles" }));
  await userEvent.click(screen.getByRole("button", { name: "ALL" }));
  expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(2);
});
