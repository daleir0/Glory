from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.narrative.item import NarrativeItem
from glory_hype.server import create_app


def seeded(tmp_path):
    import time
    base = int(time.time() * 1000)
    s = Store(str(tmp_path / "s.db"))
    s.insert_narrative_item(NarrativeItem(ts=base - 1000, source="news",
        reliability_weight=0.7, title="HYPE ATH", body="b", url="u"))
    s.save_conclusion({"bias": "bullish", "confidence": 0.7, "score": 70,
                       "key_drivers": ["x"], "caution_flags": [], "source_breakdown": {},
                       "based_on": [], "generated_at": 1234})
    return s


def test_narrative_endpoint(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/hype/narrative")
    assert r.status_code == 200
    body = r.json()
    assert body["items"][0]["title"] == "HYPE ATH"
    assert body["conclusion"]["bias"] == "bullish"
