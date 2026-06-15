from glory_hype.db import Store
from glory_hype.patterns.backtest import run_backtest


def _candle(ts, o, h, l, c, v=1.0):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + 3599999,
            "o": o, "h": h, "l": l, "c": c, "v": v, "n": 1}


def test_backtest_plants_and_detects(tmp_path):
    s = Store(str(tmp_path / "bt.db"))
    HR = 3600_000
    ts = 1_000_000_000_000
    # Build 120 hours: every ~10h a coil (flat) then a +5% pop = COIL_EXPANSION should score
    candles = []
    price = 100.0
    for i in range(120):
        if i % 10 == 5:
            price *= 1.05   # pop
            candles.append(_candle(ts + i * HR, price / 1.05, price, price / 1.05, price, 3.0))
        else:
            candles.append(_candle(ts + i * HR, price, price * 1.002, price * 0.998, price, 0.4))
    for c in candles:
        s.insert_candle(c)
        s.insert_ctx({"funding": 0.0, "open_interest": 1000.0, "mark_px": c["c"],
                      "oracle_px": c["c"], "mid_px": c["c"], "premium": 0.0,
                      "prev_day_px": c["c"], "day_ntl_vlm": 1.0}, ts=c["open_ts"])
    result = run_backtest(s)
    assert result["events_detected"] > 0
    assert len(s.all_pattern_stats()) > 0     # some pattern stats were written
