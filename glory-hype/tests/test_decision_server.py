from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_settings_roundtrip(tmp_path):
    app = create_app(Store(str(tmp_path / "s.db")))
    client = TestClient(app)
    assert client.get("/api/hype/settings").status_code == 200
    r = client.post("/api/hype/settings", json={"account_balance": "2000", "risk_pct": "0.02"})
    assert r.status_code == 200
    got = client.get("/api/hype/settings").json()["settings"]
    assert got["account_balance"] == "2000"
    assert got["risk_pct"] == "0.02"


def test_decision_endpoint_empty(tmp_path):
    app = create_app(Store(str(tmp_path / "d.db")))
    client = TestClient(app)
    r = client.get("/api/hype/decision")
    assert r.status_code == 200
    assert r.json()["call"] is None
