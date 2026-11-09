# Issue #13: Cboe Insights harvester — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New `harvest_cboe.py` appends Cboe Insights articles (RSS latest 25 / `--backfill N` listing pages) to `data/articles.jsonl` with `cboe-` prefixed slugs; `fetch.py` learns `.prose`.

**Architecture:** Standalone script mirroring `harvest.py`'s contract, importing `entry_row`/`slugify` from it. Downstream pipeline unchanged. Branch: `issue13-cboe-harvest`.

**Tech Stack:** requests, BeautifulSoup, xml.etree (stdlib), pytest. Branch: `issue13-cboe-harvest`.

---

### Task 1: RSS parsing + cboe- slug prefix

**Files:**
- Create: `harvest_cboe.py`, `tests/test_harvest_cboe.py`

- [ ] **Step 1: Failing tests**

```python
# tests/test_harvest_cboe.py
"""Tests for harvest_cboe.py — Cboe Insights RSS + backfill listing parsing."""
from __future__ import annotations

import harvest_cboe

RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Today's Market Take: Volatility Fades</title>
    <link>https://www.cboe.com/insights/todays-market-take-vol-fades/</link>
    <pubDate>Wed, 30 Sep 2026 14:05:00 +0000</pubDate>
    <description>&lt;p&gt;Indexes steadied as vol faded.&lt;/p&gt;</description>
  </item>
  <item>
    <title>Macro Volatility Digest: October</title>
    <link>https://www.cboe.com/insights/macro-vol-digest-october/</link>
    <pubDate>Tue, 29 Sep 2026 09:00:00 +0000</pubDate>
    <description>Digest of macro vol research.</description>
  </item>
</channel></rss>
"""


class TestParseRss:
    def test_rows_have_cboe_prefixed_slugs(self):
        rows = harvest_cboe.parse_rss(RSS_FIXTURE)
        assert [r["slug"] for r in rows] == [
            "cboe-today-s-market-take-volatility-fades",
            "cboe-macro-volatility-digest-october",
        ]

    def test_rows_match_entry_row_contract(self):
        rows = harvest_cboe.parse_rss(RSS_FIXTURE)
        r = rows[0]
        assert r["source"] == "Cboe Insights"
        assert r["stage"] == "harvested"
        assert r["posted"] == "2026-09-30"
        assert r["url"] == "https://www.cboe.com/insights/todays-market-take-vol-fades/"
        assert "vol faded" in r["blurb"]
        assert "harvested_at" in r

    def test_bad_date_is_tolerated(self):
        xml = RSS_FIXTURE.replace("Wed, 30 Sep 2026 14:05:00 +0000", "nonsense")
        rows = harvest_cboe.parse_rss(xml)
        assert rows[0]["posted"] is None
```

- [ ] **Step 2: Run, verify FAIL** — `python3 -m pytest tests/test_harvest_cboe.py -v`

- [ ] **Step 3: Implement `harvest_cboe.py`**

```python
#!/usr/bin/env python3
"""Harvest Cboe Insights articles into data/articles.jsonl.

Two routes:

  live     GET /insights/rss/ -- latest ~25 posts (daily incremental mode)
  backfill /insights/?page=N listing pages -- --backfill N walks the archive

Same jsonl contract as harvest.py; slugs are prefixed `cboe-` so Cboe and
Quantocracy artifacts never collide downstream.

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
# Cloudflare intercepts non-browser UAs; identify honestly in a comment field
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 "
      "autoquant-harvest/0.1 (research; contact: atmabuddy99@gmail.com)")


def row_from(title: str, url: str, blurb: str, posted: str | None,
             posted_raw: str) -> dict:
    row = entry_row(url, title, "Cboe Insights", blurb, posted, posted_raw)
    row["slug"] = "cboe-" + slugify(title)
    return row


def parse_rss(xml_text: str) -> list[dict]:
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
                posted = datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %z") \
                    .date().isoformat()
            except ValueError:
                pass
        if title and link:
            rows.append(row_from(title, link, desc, posted, pub))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", type=int, default=0,
                    help="pages of /insights/ listing to walk")
    ap.add_argument("--sleep", type=float, default=2.0,
                    help="seconds between requests")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data" / "articles.jsonl")
    args = ap.parse_args()
    raise SystemExit("backfill parsing implemented in Task 2")  # placeholder until Task 2
```

(For Task 1, `main` may simply call the RSS path; full wiring lands in Task 3.)

- [ ] **Step 4: Run** — `python3 -m pytest tests/test_harvest_cboe.py -v` → PASS
- [ ] **Step 5: Commit** — `git add harvest_cboe.py tests/test_harvest_cboe.py && git commit -m "harvest: Cboe Insights RSS parsing with cboe- slug prefix"`

### Task 2: backfill listing parsing

**Files:**
- Modify: `harvest_cboe.py`
- Test: `tests/test_harvest_cboe.py`

- [ ] **Step 1: Failing tests**

```python
LISTING_FIXTURE = """
<html><body>
  <a href="/insights/todays-market-take-vol-fades/">Vol Fades</a>
  <a href="/insights/macro-vol-digest-october/">Macro Digest</a>
  <a href="/insights/">Insights home</a>
  <a href="/insights/?page=2">Next</a>
  <a href="/market-data/">Unrelated</a>
</body></html>
"""


class TestParseListing:
    def test_extracts_post_urls_only(self):
        urls = harvest_cboe.parse_listing(LISTING_FIXTURE)
        assert "https://www.cboe.com/insights/todays-market-take-vol-fades/" in urls
        assert "https://www.cboe.com/insights/macro-vol-digest-october/" in urls
        assert len(urls) == 2  # home link and ?page= excluded
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
def parse_listing(html: str) -> list[str]:
    """Absolute post URLs from one /insights/?page=N listing page."""
    soup = BeautifulSoup(html, "html.parser")
    seen, out = set(), []
    for a in soup.select("a[href]"):
        href = urljoin(BASE + "/", a["href"])
        if ("/insights/" not in href or "?" in href):
            continue
        tail = href.split("/insights/", 1)[1].rstrip("/")
        if not tail:  # the section home itself
            continue
        if href not in seen:
            seen.add(href)
            out.append(href)
    return out
```

- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** — `git commit -am "harvest: Cboe backfill listing page parsing"`

### Task 3: main wiring (RSS default, backfill walk, dedupe, politeness)

**Files:**
- Modify: `harvest_cboe.py`
- Test: `tests/test_harvest_cboe.py`

- [ ] **Step 1: Failing tests**

```python
class TestMain:
    def test_rss_mode_appends_and_dedupes(self, tmp_path, monkeypatch):
        out = tmp_path / "articles.jsonl"

        class FakeResp:
            text = RSS_FIXTURE
            def raise_for_status(self): pass

        monkeypatch.setattr(harvest_cboe.requests.Session, "get",
                            lambda self, url, **k: FakeResp())
        assert harvest_cboe.main_with(["--out", str(out), "--sleep", "0"]) == 0
        first = out.read_text().splitlines()
        assert len(first) == 2
        assert harvest_cboe.main_with(["--out", str(out), "--sleep", "0"]) == 0
        assert len(out.read_text().splitlines()) == 2  # dedupe on url

    def test_backfill_mode_walks_pages(self, tmp_path, monkeypatch):
        out = tmp_path / "articles.jsonl"
        calls = []

        class FakeResp:
            def __init__(self, text): self.text = text
            def raise_for_status(self): pass

        def fake_get(self, url, **k):
            calls.append(url)
            if "rss" in url:
                return FakeResp(RSS_FIXTURE)
            return FakeResp(LISTING_FIXTURE)

        monkeypatch.setattr(harvest_cboe.requests.Session, "get", fake_get)
        rc = harvest_cboe.main_with(["--out", str(out), "--sleep", "0",
                                     "--backfill", "2"])
        assert rc == 0
        assert any("page=2" in c for c in calls)
        rows = [json.loads(l) for l in out.read_text().splitlines()]
        assert all(r["slug"].startswith("cboe-") for r in rows)
```

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement `main_with`** — mirror `harvest.py`'s `main()`: load
  seen urls from `--out`, open append handle, `emit()` dedupes + writes;
  RSS mode = `parse_rss(get(RSS))`; backfill mode = for page in 1..N, GET
  `/insights/` (page 1) / `/insights/?page=N`, per-page try/except prints to
  stderr and continues, empty page list stops, fetch each post URL page? NO —
  backfill only harvests links from listing pages (title = anchor text,
  blurb = "", posted = None) — no per-article requests. `time.sleep(--sleep)`
  between requests. Rename `main` → `main_with(argv)` with `ap.parse_args(argv)`,
  keep `main()` wrapper for `__main__`.
- [ ] **Step 4: Run** → PASS
- [ ] **Step 5: Commit** — `git commit -am "harvest: Cboe main wiring (RSS/backfill, dedupe, politeness)"`

### Task 4: fetch.py `.prose` candidate + README

**Files:**
- Modify: `fetch.py:44-45` (CANDIDATES), `README.md`
- Test: `tests/test_fetch.py` (new test class)

- [ ] **Step 1: Failing test**

```python
class TestCboeProseExtraction:
    CBOE_HTML = """
    <html><head><title>T</title></head><body>
      <div class="banner-education">Subscribe to Cboe education!</div>
      <div class="prose"><p>%s</p></div>
      <div class="disclaimer">Options involve risk and are not suitable
      for all investors.</div>
    </body></html>
    """ % ("Analysts noted that implied volatility declined across majors. " * 30)

    def test_prose_container_extracted(self):
        from fetch import extract
        title, text = extract(self.CBOE_HTML)
        assert "implied volatility declined" in text
        assert "Subscribe to Cboe education" not in text
```

(If `test_fetch.py` structures tests as classes already, match its style; the
`.prose` selector wins on density so banners/disclaimer outside it are excluded.)

- [ ] **Step 2: Run, verify FAIL**
- [ ] **Step 3: Implement** — add `".prose"` to `CANDIDATES` in `fetch.py`.
- [ ] **Step 4: Run** — `python3 -m pytest tests/test_fetch.py tests/test_harvest_cboe.py -v` → PASS
- [ ] **Step 5: README note** — under the Quantocracy harvest section:

```markdown
### Cboe Insights (second source)

`python3 harvest_cboe.py` appends the latest Cboe Insights posts (RSS) to the
same `data/articles.jsonl`; `--backfill N` walks the `/insights/` listing
archive. Slugs are prefixed `cboe-` so downstream artifacts never collide
with Quantocracy ones.
```

- [ ] **Step 6: Full suite + commit** — `python3 -m pytest tests/ -q && git commit -am "fetch: .prose extraction candidate for Cboe; README source note"`
