from glory_hype.narrative.adapters.websearch import WebSearchAdapter


def fake_parse(url):
    assert "news.google.com" in url and "hyperliquid" in url.lower()
    return type("Feed", (), {"entries": [
        {"title": "Analyst: HYPE could hit $150", "summary": "bull case",
         "link": "https://g/1", "published_parsed": (2026, 5, 29, 1, 0, 0, 0, 0, 0)},
    ]})()


def test_websearch_builds_query_and_items():
    a = WebSearchAdapter(query="hyperliquid HYPE", parse=fake_parse)
    items = a.fetch()
    assert len(items) == 1
    assert items[0].source == "websearch"
    assert items[0].reliability_weight == 0.6
    assert items[0].url == "https://g/1"


def test_websearch_failure_returns_empty():
    def boom(url):
        raise OSError("nope")
    assert WebSearchAdapter(parse=boom).fetch() == []
