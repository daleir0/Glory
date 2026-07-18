from glory_hype.narrative.item import NarrativeItem, content_hash, dedupe_items


def test_content_hash_stable_and_distinct():
    h1 = content_hash("news", "HYPE hits ATH", "https://x/1")
    h2 = content_hash("news", "HYPE hits ATH", "https://x/1")
    h3 = content_hash("news", "HYPE dumps", "https://x/2")
    assert h1 == h2
    assert h1 != h3
    assert isinstance(h1, str) and len(h1) == 64  # sha256 hex


def test_item_autocomputes_hash():
    it = NarrativeItem(ts=1000, source="news", reliability_weight=0.7,
                       title="HYPE hits ATH", body="...", url="https://x/1")
    assert it.hash == content_hash("news", "HYPE hits ATH", "https://x/1")


def test_dedupe_keeps_first_of_each_hash():
    a = NarrativeItem(ts=1, source="news", reliability_weight=0.7,
                      title="same", body="b1", url="u")
    b = NarrativeItem(ts=2, source="news", reliability_weight=0.7,
                      title="same", body="b2", url="u")  # same hash as a
    c = NarrativeItem(ts=3, source="news", reliability_weight=0.7,
                      title="diff", body="b3", url="u2")
    out = dedupe_items([a, b, c])
    assert len(out) == 2
    assert out[0].body == "b1"  # first wins
