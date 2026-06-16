from glory_hype.db import Store


def test_pending_then_finalize(tmp_path):
    s = Store(str(tmp_path / "p.db"))
    s.insert_pending_chart_read(ts=1000, image_path="charts/a.png")
    pend = s.pending_chart_reads()
    assert len(pend) == 1
    assert pend[0]["ts"] == 1000
    assert pend[0]["image_path"] == "charts/a.png"
    # latest_chart_read ignores pending rows
    assert s.latest_chart_read() is None

    s.finalize_chart_read(1000, {"ts": 1000, "timeframe": "1h", "trend": "up",
                                 "current_price": 65.0, "image_path": "charts/a.png",
                                 "support_levels": [64.0]})
    assert s.pending_chart_reads() == []
    latest = s.latest_chart_read()
    assert latest["trend"] == "up"
    assert latest["support_levels"] == [64.0]


def test_existing_read_insert_still_works(tmp_path):
    s = Store(str(tmp_path / "p2.db"))
    s.insert_chart_read({"ts": 5, "timeframe": "1d", "trend": "down",
                         "current_price": 64.0, "image_path": None})
    assert s.latest_chart_read()["ts"] == 5      # status defaults to "read"
    assert s.pending_chart_reads() == []


def test_finalize_via_record(tmp_path):
    from glory_hype.chart.record import finalize_chart_read
    s = Store(str(tmp_path / "p3.db"))
    s.insert_pending_chart_read(ts=2000, image_path="charts/b.png")
    read = finalize_chart_read(s, 2000, {"timeframe": "4h", "trend": "down",
                                         "current_price": 64.2})
    assert read.trend == "down"
    assert read.image_path == "charts/b.png"     # preserved from pending row
    assert s.latest_chart_read()["timeframe"] == "4h"
    assert s.pending_chart_reads() == []
