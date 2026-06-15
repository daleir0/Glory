from glory_hype.narrative.adapters.news import NewsAdapter


class FakeEntry(dict):
    __getattr__ = dict.get


def fake_parse(url):
    return type("Feed", (), {"entries": [
        {"title": "Hyperliquid HYPE hits new ATH", "summary": "big move",
         "link": "https://n/1", "published_parsed": (2026, 5, 29, 12, 0, 0, 0, 0, 0)},
        {"title": "Bitcoin chops sideways", "summary": "no hype here",
         "link": "https://n/2", "published_parsed": (2026, 5, 29, 12, 5, 0, 0, 0, 0)},
    ]})()


def test_news_filters_to_hype_mentions():
    a = NewsAdapter(feeds=["http://feed"], parse=fake_parse)
    items = a.fetch()
    assert len(items) == 1
    assert "Hyperliquid" in items[0].title
    assert items[0].source == "news"
    assert items[0].reliability_weight == 0.7
    assert items[0].url == "https://n/1"


def test_news_network_failure_returns_empty():
    def boom(url):
        raise OSError("dns fail")
    assert NewsAdapter(feeds=["http://feed"], parse=boom).fetch() == []
