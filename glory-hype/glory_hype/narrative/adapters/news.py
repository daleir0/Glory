"""Crypto-outlet RSS news adapter."""

import calendar
import time

from glory_hype.narrative.item import NarrativeItem
from glory_hype.narrative.weights import weight_for

DEFAULT_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]
import re as _re


def _matches(text: str) -> bool:
    if "hyperliquid" in text.lower():
        return True
    if "$hype" in text.lower():
        return True
    return _re.search(r"\bHYPE\b", text) is not None


def _entry_ts(entry) -> int:
    pp = entry.get("published_parsed")
    if pp:
        return int(calendar.timegm(pp) * 1000)
    return int(time.time() * 1000)


class NewsAdapter:
    source = "news"

    def __init__(self, feeds=None, parse=None):
        self.feeds = feeds or DEFAULT_FEEDS
        if parse is None:
            import feedparser
            parse = feedparser.parse
        self.parse = parse

    def fetch(self) -> list[NarrativeItem]:
        items = []
        for url in self.feeds:
            try:
                feed = self.parse(url)
            except Exception:
                continue
            for e in getattr(feed, "entries", []):
                title = e.get("title", "")
                summary = e.get("summary", "")
                if not (_matches(title) or _matches(summary)):
                    continue
                items.append(NarrativeItem(
                    ts=_entry_ts(e), source=self.source,
                    reliability_weight=weight_for(self.source),
                    title=title, body=summary, url=e.get("link")))
        return items
