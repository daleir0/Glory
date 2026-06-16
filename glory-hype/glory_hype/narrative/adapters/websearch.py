"""Keyless web search via Google News RSS query."""

import urllib.parse

from glory_hype.narrative.adapters.news import _entry_ts, _matches  # reuse
from glory_hype.narrative.item import NarrativeItem
from glory_hype.narrative.weights import weight_for

_BASE = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


class WebSearchAdapter:
    source = "websearch"

    def __init__(self, query: str = "hyperliquid HYPE", parse=None):
        self.query = query
        if parse is None:
            import feedparser
            parse = feedparser.parse
        self.parse = parse

    def _url(self) -> str:
        return _BASE.format(q=urllib.parse.quote(self.query))

    def fetch(self) -> list[NarrativeItem]:
        try:
            feed = self.parse(self._url())
        except Exception:
            return []
        items = []
        for e in getattr(feed, "entries", []):
            title = e.get("title", "")
            summary = e.get("summary", "")
            # Google News already scoped by query; keep all entries.
            items.append(NarrativeItem(
                ts=_entry_ts(e), source=self.source,
                reliability_weight=weight_for(self.source),
                title=title, body=summary, url=e.get("link")))
        return items
