from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def seeded(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.insert_ctx({"funding": 0.0001, "open_interest": 10.0, "mark_px": 62.0,
                  "oracle_px": 62.1, "mid_px": 62.05, "premium": 0.0,
                  "prev_day_px": 56.0, "day_ntl_vlm": 1.0}, ts=1000)
    s.insert_candle({"interval": "1m", "open_ts": 0, "close_ts": 59, "o": 1.0,
                     "h": 2.0, "l": 0.5, "c": 1.5, "v": 9.0, "n": 4})
    s.insert_trade({"ts": 2000, "px": 62.0, "sz": 1000.0, "side": "B", "tid": 7,
                    "ntl": 62000.0, "is_large": True})
    return s


def test_snapshot_endpoint(tmp_path):
    app = create_app({"hype": seeded(tmp_path)})
    client = TestClient(app)
    r = client.get("/api/hype/snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["ctx"]["mark_px"] == 62.0
    assert body["large_trades"][0]["tid"] == 7
    assert body["candles_1m"][-1]["c"] == 1.5


def test_dashboard_served(tmp_path):
    app = create_app({"hype": seeded(tmp_path)})
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "HYPE" in r.text


def test_health_reports_freshness(tmp_path):
    app = create_app({"hype": seeded(tmp_path)})
    client = TestClient(app)
    r = client.get("/api/hype/health")
    assert r.status_code == 200
    assert "ctx_ts" in r.json()


def test_unknown_asset_returns_404(tmp_path):
    app = create_app({"hype": seeded(tmp_path)})
    client = TestClient(app)
    r = client.get("/api/xyz/snapshot")
    assert r.status_code == 404
    assert "unknown asset" in r.json()["detail"]


def test_list_assets(tmp_path):
    app = create_app({"hype": seeded(tmp_path)})
    client = TestClient(app)
    r = client.get("/api/assets")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["slug"] == "hype"
    assert items[0]["price"] == 62.0


def test_backward_compat_bare_store(tmp_path):
    app = create_app(seeded(tmp_path))
    client = TestClient(app)
    r = client.get("/api/hype/snapshot")
    assert r.status_code == 200
