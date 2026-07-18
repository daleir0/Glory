import time
from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_events_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    now = int(time.time() * 1000)
    s.insert_event({"date_ms": now + 2 * 86400_000, "type": "unlock",
                    "label": "future unlock", "magnitude_pct": 2.5,
                    "magnitude_usd": 6.8e8, "source_url": "", "notes": ""})
    s.upsert_event_study({"type": "unlock", "n": 4, "median_pre": -3.0,
                          "median_post": 4.0, "median_trough": -6.0, "median_peak": 5.0,
                          "spread_json": "{}", "confidence_label": "small-sample composite (N=4)",
                          "computed_at": now})
    client = TestClient(create_app(s))
    r = client.get("/api/hype/events")
    assert r.status_code == 200
    body = r.json()
    assert len(body["upcoming"]) == 1
    assert body["upcoming"][0]["type"] == "unlock"
    assert any(p["type"] == "unlock" for p in body["playbook"])
