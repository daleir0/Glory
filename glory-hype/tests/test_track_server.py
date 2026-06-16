from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_track_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.update_call_outcome(1000, {"status": "win", "exit_price": 110.0,
                                 "r_multiple": 2.0, "ambiguous": False})
    app = create_app(s)
    client = TestClient(app)
    r = client.get("/api/hype/track")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["wins"] == 1
    assert body["stats"]["win_rate"] == 1.0
    assert len(body["recent"]) == 1
    assert body["recent"][0]["status"] == "win"
