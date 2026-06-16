from glory_hype.db import Store


def _read(ts, tf="1h", trend="up", px=65.0):
    return {"ts": ts, "timeframe": tf, "trend": trend, "current_price": px,
            "support_levels": [64.0], "resistance_levels": [66.0],
            "patterns": ["flag"], "indicators": {"rsi": 70}, "image_path": None,
            "notes": "n"}


def test_insert_and_latest(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    s.insert_chart_read(_read(1000))
    s.insert_chart_read(_read(2000, trend="down", px=64.0))
    latest = s.latest_chart_read()
    assert latest["ts"] == 2000
    assert latest["trend"] == "down"
    assert latest["support_levels"] == [64.0]      # JSON round-trips
    assert latest["indicators"] == {"rsi": 70}


def test_recent_filters_by_time(tmp_path):
    s = Store(str(tmp_path / "c2.db"))
    s.insert_chart_read(_read(100))
    s.insert_chart_read(_read(9000))
    rows = s.recent_chart_reads(since_ts=5000)
    assert [r["ts"] for r in rows] == [9000]


def test_latest_none_when_empty(tmp_path):
    s = Store(str(tmp_path / "c3.db"))
    assert s.latest_chart_read() is None
