import time
from glory_hype.db import Store
from glory_hype.narrative.item import NarrativeItem
from glory_hype.narrative.proxy_client import ProxyError
from glory_hype.narrative.synthesize import Synthesizer, build_prompt


def _seed(store):
    base = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 65.0,
                      "oracle_px": 65.0, "mid_px": 65.0, "premium": 0.0,
                      "prev_day_px": 57.0, "day_ntl_vlm": 1e9}, ts=base - 2000)
    store.insert_narrative_item(NarrativeItem(ts=base - 1000, source="onchain",
        reliability_weight=1.0, title="OI surged +12%", body="...", url=None))
    store.insert_narrative_item(NarrativeItem(ts=base - 500, source="news",
        reliability_weight=0.7, title="HYPE ETF inflows", body="...", url="u"))


class FakeProxyOK:
    def chat(self, messages, max_tokens=1500):
        return ('{"bias":"bullish","confidence":0.7,'
                '"key_drivers":["ETF inflows","OI surge"],'
                '"caution_flags":["extended"],'
                '"source_breakdown":{"onchain":1,"news":1}}')


class FakeProxyDown:
    def chat(self, messages, max_tokens=1500):
        raise ProxyError("proxy down")


def test_build_prompt_includes_weights_and_ctx(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    _seed(s)
    items = s.recent_narrative_items(since_ts=0)
    msgs = build_prompt(items, ctx=s.latest_ctx())
    blob = " ".join(m["content"] for m in msgs)
    assert "reliability" in blob.lower()
    assert "onchain" in blob.lower() and "1.0" in blob
    assert "65.0" in blob  # market context price present
    assert "json" in blob.lower()


def test_synthesize_ok_persists_conclusion(tmp_path):
    s = Store(str(tmp_path / "p2.db"))
    _seed(s)
    syn = Synthesizer(s, proxy=FakeProxyOK())
    c = syn.synthesize()
    assert c.bias == "bullish"
    assert c.score == 70
    assert len(c.based_on) == 2          # both items referenced
    assert s.latest_conclusion()["bias"] == "bullish"   # persisted


def test_synthesize_proxy_down_is_graceful(tmp_path):
    s = Store(str(tmp_path / "p3.db"))
    _seed(s)
    c = Synthesizer(s, proxy=FakeProxyDown()).synthesize()
    assert c.bias == "neutral"
    assert c.confidence == 0.0
    assert "unavailable" in " ".join(c.caution_flags).lower()


def test_build_prompt_caps_and_ranks():
    from glory_hype.narrative.synthesize import build_prompt, MAX_PROMPT_ITEMS
    items = []
    # 80 low-weight social items + 1 high-weight onchain item
    for i in range(80):
        items.append({"source": "social", "reliability_weight": 0.3, "ts": 1000 + i,
                      "title": f"noise {i}", "body": "x", "hash": f"s{i}"})
    items.append({"source": "onchain", "reliability_weight": 1.0, "ts": 1,
                  "title": "OI surged", "body": "fact", "hash": "o1"})
    msgs = build_prompt(items, ctx=None)
    user = msgs[1]["content"]
    item_lines = [l for l in user.splitlines() if l.strip().startswith("[")]
    assert len(item_lines) <= MAX_PROMPT_ITEMS
    # the onchain (1.0) item must survive the cap ahead of social noise
    assert any("OI surged" in l for l in item_lines)
