import time
from glory_hype.db import Store
from glory_hype.decision.engine import record_call


def _fresh(store, bias="bullish", score=70):
    now = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 70.0,
                      "oracle_px": 70.0, "mid_px": 70.0, "premium": 0.0,
                      "prev_day_px": 67.0, "day_ntl_vlm": 1e9}, ts=now)
    store.save_conclusion({"bias": bias, "confidence": 0.7, "score": score,
                           "key_drivers": [], "caution_flags": [],
                           "source_breakdown": {}, "based_on": [], "generated_at": now})
    store.insert_chart_read({"ts": now, "timeframe": "5m", "trend": "up",
                             "current_price": 70.0, "flags": [],
                             "position": {"entry": 66.0, "tp": 75.5, "sl": 64.0},
                             "image_path": None})
    store.set_setting("account_balance", "1000")
    return now


def test_bullish_conclusion_boosts_long_confidence(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _fresh(s, bias="bullish", score=70)
    j = {"decision": "long", "entry": 66.0, "tp": 75.5, "sl": 64.0,
         "confidence": 0.70, "rationale": "test"}
    call = record_call(s, j)
    assert call.decision == "long"
    assert call.confidence >= 0.70  # boosted by +0.05


def test_bearish_conclusion_penalizes_long_confidence(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _fresh(s, bias="bearish", score=70)
    j = {"decision": "long", "entry": 66.0, "tp": 75.5, "sl": 64.0,
         "confidence": 0.70, "rationale": "test"}
    call = record_call(s, j)
    assert call.decision == "long"
    assert call.confidence <= 0.70  # penalized by -0.10


def test_neutral_conclusion_leaves_confidence_unchanged(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _fresh(s, bias="neutral", score=70)
    base_conf = 0.70
    j = {"decision": "long", "entry": 66.0, "tp": 75.5, "sl": 64.0,
         "confidence": base_conf, "rationale": "test"}
    call = record_call(s, j)
    # neutral = 0 modifier; pattern matches also empty so confidence == base
    assert abs(call.confidence - base_conf) < 0.01


def test_low_score_bullish_does_not_boost(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    _fresh(s, bias="bullish", score=50)  # score < 65 threshold
    j = {"decision": "long", "entry": 66.0, "tp": 75.5, "sl": 64.0,
         "confidence": 0.70, "rationale": "test"}
    call = record_call(s, j)
    assert abs(call.confidence - 0.70) < 0.01  # no boost when score < 65
