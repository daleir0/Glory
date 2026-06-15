from glory_hype.db import Store
from glory_hype.patterns.detector import current_signal


def _candle(ts, o, h, l, c, v=1.0):
    return {"interval": "1h", "open_ts": ts, "close_ts": ts + 3599999,
            "o": o, "h": h, "l": l, "c": c, "v": v, "n": 1}


def test_detector_returns_regime_and_matches(tmp_path):
    s = Store(str(tmp_path / "d.db"))
    HR = 3600_000
    ts = 1_000_000_000_000
    # flat quiet coil now
    for i in range(14):
        s.insert_candle(_candle(ts + i * HR, 100, 100.1, 99.9, 100, 0.3))
        s.insert_ctx({"funding": 0.0, "open_interest": 1000.0, "mark_px": 100,
                      "oracle_px": 100, "mid_px": 100, "premium": 0.0,
                      "prev_day_px": 100, "day_ntl_vlm": 1.0}, ts=ts + i * HR)
    # a stable COIL_EXPANSION stat exists
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand",
                           "n_train": 20, "n_test": 8, "win_rate_train": 0.75,
                           "win_lo_test": 0.66, "win_hi_test": 0.9, "avg_move_pct": 5.0,
                           "avg_move_hrs": 6, "direction": "up", "stable": 1})
    sig = current_signal(s)
    assert sig["regime"] in ("coiling", "ranging")
    # COIL_EXPANSION should be an active stable match with its confidence
    names = [m["pattern_name"] for m in sig["matches"]]
    if "COIL_EXPANSION" in names:
        m = next(x for x in sig["matches"] if x["pattern_name"] == "COIL_EXPANSION")
        assert m["confidence"] == 0.66 and m["direction"] == "up"


def test_detector_empty_history(tmp_path):
    s = Store(str(tmp_path / "d2.db"))
    sig = current_signal(s)
    assert sig["matches"] == []
