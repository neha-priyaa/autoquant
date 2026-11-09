#!/usr/bin/env python3
"""Harvest Cboe Insights articles into data/articles.jsonl.

Two routes, mirroring harvest.py's contract:

  live     GET /insights/rss/ -- latest ~25 posts (daily incremental mode)
  backfill /insights/?page=N listing pages -- --backfill N walks the archive

Same jsonl fields as harvest.py's entry_row(); slugs are prefixed `cboe-` so
Cboe and Quantocracy artifacts never collide downstream. fetch.py handles the
full-text pull via its `.prose` extraction candidate.

    python3 harvest_cboe.py                  # latest 25 (daily use)
    python3 harvest_cboe.py --backfill 10    # walk the listing archive
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from harvest import entry_row, slugify

ROOT = Path(__file__).resolve().parent
BASE = "https://www.cboe.com"
RSS = BASE + "/insights/rss/"
# Cloudflare intercepts non-browser UAs, so the agent identifies itself in a
# comment field appended to a browser-shaped UA string.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
      "autoquant-harvest/0.1 (research; contact: atmabuddy99@gmail.com)")


def row_from(title: str, url: str, blurb: str, posted: str | None,
             posted_raw: str) -> dict:
    """Cboe-flavored entry_row: fixed source + cboe- prefixed slug."""
    row = entry_row(url, title, "Cboe Insights", blurb, posted, posted_raw)
    row["slug"] = "cboe-" + slugify(title)
    return row


def parse_rss(xml_text: str) -> list[dict]:
    """Rows from the /insights/rss/ feed (latest ~25 posts)."""
    root = ET.fromstring(xml_text)
    rows = []
    for item in root.iter("item"):
        title = " ".join((item.findtext("title") or "").split())
        link = (item.findtext("link") or "").strip()
        desc = " ".join((item.findtext("description") or "").split())
        pub = (item.findtext("pubDate") or "").strip()
        posted = None
        if pub:
            try:
                posted = datetime.strptime(
                    pub, "%a, %d %b %Y %H:%M:%S %z").date().isoformat()
            except ValueError:
                pass
        if title and link:
            rows.append(row_from(title, link, desc, posted, pub))
    return rows


def parse_listing(html: str) -> list[str]:
    """Absolute post URLs from one /insights/?page=N listing page."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    out: list[str] = []
    for a in soup.select("a[href]"):
        href = urljoin(BASE + "/", a["href"])
        if "/insights/" not in href or "?" in href:
            continue
        if not href.split("/insights/", 1)[1].rstrip("/"):
            continue  # the section home itself
        if href not in seen:
            seen.add(href)
            out.append(href)
    return out


def listing_rows(html: str) -> list[dict]:
    """Rows for one listing page: link + anchor text, no per-article fetches."""
    post_urls = set(parse_listing(html))
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.select("a[href]"):
        href = urljoin(BASE + "/", a["href"])
        if href not in post_urls or not a.get_text(strip=True):
            continue
        title = " ".join(a.get_text(" ", strip=True).split())
        rows.append(row_from(title, href, "", None, ""))
    return rows


def get(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def main_with(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0,
                    help="pages of /insights/ listing to walk (default: RSS)")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between requests")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "articles.jsonl")
    args = ap.parse_args(argv)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    if args.out.exists():
        with args.out.open() as fh:
            for line in fh:
                if line.strip():
                    seen.add(json.loads(line)["url"])
    print(f"{len(seen)} urls already known")

    session = requests.Session()
    session.headers["User-Agent"] = UA

    new = 0
    with args.out.open("a") as fh:

        def emit(rows: list[dict], label: str) -> None:
            nonlocal new
            added = 0
            for row in rows:
                if row["url"] in seen:
                    continue
                seen.add(row["url"])
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                added += 1
            new += added
            print(f"{label}: {len(rows)} entries, {added} new")

        if not args.backfill:
            emit(parse_rss(get(session, RSS)), "rss")
        else:
            for page in range(1, args.backfill + 1):
                url = BASE + "/insights/" if page == 1 \
                    else BASE + f"/insights/?page={page}"
                try:
                    rows = listing_rows(get(session, url))
                except Exception as exc:  # keep long backfills alive
                    print(f"insights p{page}: {exc}", file=sys.stderr)
                    continue
                if not rows:
                    print(f"insights p{page}: no posts — stopping")
                    break
                emit(rows, f"p{page}")
                time.sleep(args.sleep)

    print(f"\n{new} new articles -> {args.out}")
    return 0


def _listing_rows(session: requests.Session, url: str) -> list[dict]:
    """Rows for one listing page: link + anchor text, no extra fetches."""
    html = get(session, url)
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for a in soup.select("a[href]"):
        href = urljoin(BASE + "/", a["href"])
        if href not in parse_listing(html) or not a.get_text(strip=True):
            continue
        rows.append(row_from(" ".join(a.get_text(" ", strip=True).split()),
                             href, "", None, ""))
    return rows


def main() -> int:
    return main_with()


if __name__ == "__main__":
    raise SystemExit(main())
