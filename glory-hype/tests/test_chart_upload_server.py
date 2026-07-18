from fastapi.testclient import TestClient
from glory_hype.db import Store
from glory_hype.server import create_app


def test_upload_creates_pending_and_lists(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    app = create_app(store, charts_dir=str(tmp_path / "charts"))
    client = TestClient(app)
    r = client.post("/api/hype/chart/upload",
                    files={"file": ("chart.png", b"\x89PNG fake", "image/png")})
    assert r.status_code == 200
    ts = r.json()["ts"]
    pend = client.get("/api/hype/chart/pending").json()["pending"]
    assert len(pend) == 1
    assert pend[0]["ts"] == ts
    # image saved to disk
    from pathlib import Path
    assert Path(pend[0]["image_path"]).exists()


def test_upload_rejects_non_image(tmp_path):
    app = create_app(Store(str(tmp_path / "s2.db")), charts_dir=str(tmp_path / "c"))
    client = TestClient(app)
    r = client.post("/api/hype/chart/upload",
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
