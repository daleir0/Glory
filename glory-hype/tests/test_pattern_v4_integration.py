import time
from glory_hype.db import Store
from glory_hype.decision.engine import record_call


def _fresh(s):
    now = int(time.time() * 1000)
    s.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 67.5,
                  "oracle_px": 67.5, "mid_px": 67.5, "premium": 0.0,
                  "prev_day_px": 64.0, "day_ntl_vlm": 1e9}, ts=now)
    s.save_conclusion({"bias": "bullish", "confidence": 0.7, "score": 70,
                       "key_drivers": [], "caution_flags": [], "source_breakdown": {},
                       "based_on": [], "generated_at": now})
    s.insert_chart_read({"ts": now, "timeframe": "5m", "trend": "up", "current_price": 67.5,
                         "flags": [], "position": {"entry": 67.4, "tp": 68.2, "sl": 66.7},
                         "image_path": None})
    s.set_setting("account_balance", "1000")
    return now


def test_call_inputs_carry_pattern_signal(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    assert "pattern_signal" in call.inputs


def test_agreeing_pattern_raises_confidence(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    _fresh(s)
    # base call confidence
    base = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"}).confidence
    # plant a stable bullish pattern + enough 1h candles for the detector to match
    HR = 3600_000; now = int(time.time() * 1000)
    for i in range(14):
        s.insert_candle({"interval": "1h", "open_ts": now - (14 - i) * HR,
                         "close_ts": now - (14 - i) * HR + 3599999, "o": 100,
                         "h": 100.1, "l": 99.9, "c": 100, "v": 0.3, "n": 1})
    s.upsert_pattern_stat({"pattern_name": "COIL_EXPANSION", "source": "hand", "n_train": 20,
                           "n_test": 8, "win_rate_train": 0.8, "win_lo_test": 0.7,
                           "win_hi_test": 0.95, "avg_move_pct": 5.0, "avg_move_hrs": 6,
                           "direction": "up", "stable": 1})
    boosted = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                              "confidence": 0.6, "rationale": "x"}).confidence
    assert boosted >= base    # agreeing bullish pattern should not lower it
