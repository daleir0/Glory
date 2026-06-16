from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def client(tmp_path):
    return TestClient(create_app(Store(str(tmp_path / "s.db"))))


def test_calc_endpoint_ok(tmp_path):
    r = client(tmp_path).post("/api/calc", json={
        "mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 95.0,
        "direction": "long", "leverage": 10, "margin": 500.0})
    assert r.status_code == 200
    body = r.json()
    assert body["position_notional"] == 5000.0
    assert body["rr"] == 2.0


def test_calc_endpoint_bad_input_400(tmp_path):
    r = client(tmp_path).post("/api/calc", json={
        "mode": "margin", "entry": 0, "tp": 1, "sl": 1,
        "direction": "long", "leverage": 10, "margin": 500.0})
    assert r.status_code == 400
    assert "entry" in r.json()["detail"].lower()
