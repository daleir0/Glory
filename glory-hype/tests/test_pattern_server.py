from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_patterns_endpoint(tmp_path):
    s = Store(str(tmp_path / "s.db"))
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand", "n_train": 20,
                           "n_test": 8, "win_rate_train": 0.75, "win_lo_test": 0.66,
                           "win_hi_test": 0.9, "avg_move_pct": 5.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    client = TestClient(create_app(s))
    r = client.get("/api/hype/patterns")
    assert r.status_code == 200
    body = r.json()
    assert "regime" in body and "matches" in body and "library" in body
    assert any(p["pattern_name"] == "COIL_EXPANSION" for p in body["library"])
