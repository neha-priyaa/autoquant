# tests/test_harvest_cboe.py
"""Tests for harvest_cboe.py — Cboe Insights RSS + backfill listing parsing."""
from __future__ import annotations

import json

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

LISTING_FIXTURE = """
<html><body>
  <a href="/insights/todays-market-take-vol-fades/">Vol Fades</a>
  <a href="/insights/macro-vol-digest-october/">Macro Digest</a>
  <a href="/insights/">Insights home</a>
  <a href="/insights/?page=2">Next</a>
  <a href="/market-data/">Unrelated</a>
</body></html>
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


class TestParseListing:
    def test_extracts_post_urls_only(self):
        urls = harvest_cboe.parse_listing(LISTING_FIXTURE)
        assert "https://www.cboe.com/insights/todays-market-take-vol-fades/" in urls
        assert "https://www.cboe.com/insights/macro-vol-digest-october/" in urls
        assert len(urls) == 2  # home link and ?page= excluded


class TestMain:
    def test_rss_mode_appends_and_dedupes(self, tmp_path, monkeypatch):
        out = tmp_path / "articles.jsonl"

        class FakeResp:
            text = RSS_FIXTURE

            def raise_for_status(self):
                pass

        monkeypatch.setattr(harvest_cboe.requests.Session, "get",
                            lambda self, url, **k: FakeResp())
        assert harvest_cboe.main_with(["--out", str(out), "--sleep", "0"]) == 0
        assert len(out.read_text().splitlines()) == 2
        assert harvest_cboe.main_with(["--out", str(out), "--sleep", "0"]) == 0
        assert len(out.read_text().splitlines()) == 2  # dedupe on url

    def test_backfill_mode_walks_pages(self, tmp_path, monkeypatch):
        out = tmp_path / "articles.jsonl"
        calls = []

        class FakeResp:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                pass

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
        assert rows
        assert all(r["slug"].startswith("cboe-") for r in rows)

    def test_backfill_survives_page_error(self, tmp_path, monkeypatch):
        out = tmp_path / "articles.jsonl"

        class FakeResp:
            def __init__(self, text):
                self.text = text

            def raise_for_status(self):
                pass

        def fake_get(self, url, **k):
            if "page=1" in url:
                raise ConnectionError("boom")
            if "rss" in url:
                return FakeResp(RSS_FIXTURE)
            return FakeResp(LISTING_FIXTURE)

        monkeypatch.setattr(harvest_cboe.requests.Session, "get", fake_get)
        rc = harvest_cboe.main_with(["--out", str(out), "--sleep", "0",
                                     "--backfill", "2"])
        assert rc == 0
        assert out.exists()
