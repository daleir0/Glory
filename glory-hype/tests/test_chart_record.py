from pathlib import Path
from glory_hype.db import Store
from glory_hype.chart.record import record_chart_read


def test_record_saves_image_and_row(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    charts = tmp_path / "charts"
    read = record_chart_read(
        s, {"timeframe": "1h", "trend": "up", "current_price": 65.0},
        image_bytes=b"\x89PNG fake", charts_dir=str(charts), ts=1234)
    assert read.timeframe == "1h"
    assert read.image_path is not None
    assert Path(read.image_path).exists()
    assert Path(read.image_path).read_bytes() == b"\x89PNG fake"
    assert s.latest_chart_read()["ts"] == 1234


def test_record_without_image(tmp_path):
    s = Store(str(tmp_path / "r2.db"))
    read = record_chart_read(s, {"trend": "down"}, image_bytes=None,
                             charts_dir=str(tmp_path / "charts"), ts=7)
    assert read.image_path is None
    assert s.latest_chart_read()["trend"] == "down"


def test_record_image_failure_still_persists(tmp_path, monkeypatch):
    s = Store(str(tmp_path / "r3.db"))
    import glory_hype.chart.record as rec

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(rec, "_write_image", boom)
    read = record_chart_read(s, {"trend": "range"}, image_bytes=b"x",
                             charts_dir=str(tmp_path / "charts"), ts=3)
    assert read.image_path is None          # save failed, gracefully None
    assert s.latest_chart_read()["ts"] == 3  # row still persisted
