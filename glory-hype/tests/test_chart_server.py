from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def seeded(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_chart_read({"ts": 1234, "timeframe": "1h", "trend": "up",
                         "current_price": 65.6, "support_levels": [64.0],
                         "resistance_levels": [66.8], "patterns": ["flag"],
                         "indicators": {"rsi": 68}, "image_path": None,
                         "notes": "extended"})
    return s


def test_chart_endpoint(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/hype/chart")
    assert r.status_code == 200
    body = r.json()
    assert body["read"]["trend"] == "up"
    assert body["read"]["support_levels"] == [64.0]


def test_chart_endpoint_empty(tmp_path):
    app = create_app(Store(str(tmp_path / "e.db")))
    client = TestClient(app)
    r = client.get("/api/hype/chart")
    assert r.status_code == 200
    assert r.json()["read"] is None
