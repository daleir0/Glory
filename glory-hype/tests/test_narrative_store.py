from glory_hype.db import Store
from glory_hype.narrative.item import NarrativeItem


def test_insert_and_read_items_deduped(tmp_path):
    s = Store(str(tmp_path / "n.db"))
    a = NarrativeItem(ts=1000, source="news", reliability_weight=0.7,
                      title="HYPE ATH", body="b", url="u1")
    s.insert_narrative_item(a)
    s.insert_narrative_item(a)  # same hash -> ignored
    rows = s.recent_narrative_items(since_ts=0)
    assert len(rows) == 1
    assert rows[0]["source"] == "news"
    assert rows[0]["title"] == "HYPE ATH"


def test_recent_items_filters_by_time(tmp_path):
    s = Store(str(tmp_path / "n2.db"))
    s.insert_narrative_item(NarrativeItem(ts=100, source="news",
        reliability_weight=0.7, title="old", body="b", url="o"))
    s.insert_narrative_item(NarrativeItem(ts=9000, source="news",
        reliability_weight=0.7, title="new", body="b", url="n"))
    rows = s.recent_narrative_items(since_ts=5000)
    assert [r["title"] for r in rows] == ["new"]


def test_save_and_get_latest_conclusion(tmp_path):
    s = Store(str(tmp_path / "n3.db"))
    s.save_conclusion({"bias": "bullish", "confidence": 0.8, "score": 64,
                       "key_drivers": ["a"], "caution_flags": ["b"],
                       "source_breakdown": {"news": 1}, "based_on": ["h1"],
                       "generated_at": 1234})
    c = s.latest_conclusion()
    assert c["bias"] == "bullish"
    assert c["key_drivers"] == ["a"]      # round-trips JSON
    assert c["generated_at"] == 1234
