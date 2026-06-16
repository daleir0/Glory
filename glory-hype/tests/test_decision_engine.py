import time
from glory_hype.db import Store
from glory_hype.decision.engine import record_call


def _fresh(store):
    now = int(time.time() * 1000)
    store.insert_ctx({"funding": 0.0001, "open_interest": 1e6, "mark_px": 67.5,
                      "oracle_px": 67.5, "mid_px": 67.5, "premium": 0.0,
                      "prev_day_px": 64.0, "day_ntl_vlm": 1e9}, ts=now)
    store.save_conclusion({"bias": "bullish", "confidence": 0.7, "score": 70,
                           "key_drivers": [], "caution_flags": [],
                           "source_breakdown": {}, "based_on": [], "generated_at": now})
    store.insert_chart_read({"ts": now, "timeframe": "5m", "trend": "range",
                             "current_price": 67.5, "flags": [],
                             "position": {"entry": 67.4, "tp": 68.2, "sl": 66.7},
                             "image_path": None})
    store.set_setting("account_balance", "1000")
    return now


def test_sized_long_call(tmp_path):
    s = Store(str(tmp_path / "e.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7, "rationale": "aligned"})
    # R:R = (68.2-67.4)/(67.4-66.7) = 0.8/0.7 = 1.14 < MIN_RR=1.5, so blocked
    assert call.decision == "no_trade"
    assert any("r:r" in g.lower() or "reward" in g.lower() for g in call.gates_failed)
    assert s.latest_trade_call()["decision"] == "no_trade"


def test_position_value_adds_to_equity_for_sizing(tmp_path):
    s = Store(str(tmp_path / "eq.db"))
    _fresh(s)                                   # account_balance=1000
    s.set_setting("position_value", "1000")     # total equity = 2000
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7, "rationale": "aligned"})
    # R:R = 1.14 < MIN_RR=1.5, so blocked (same as test_sized_long_call)
    assert call.decision == "no_trade"
    assert any("r:r" in g.lower() or "reward" in g.lower() for g in call.gates_failed)


def test_gate_blocks_when_chart_flagged(tmp_path):
    s = Store(str(tmp_path / "e2.db"))
    _fresh(s)
    # overwrite chart read with a flagged one
    now = int(time.time() * 1000)
    s.insert_chart_read({"ts": now + 1, "timeframe": "5m", "trend": "range",
                         "current_price": 99.0, "flags": ["diverges 40%"],
                         "position": {"entry": 99, "tp": 100, "sl": 98},
                         "image_path": None})
    call = record_call(s, {"decision": "long", "entry": 99, "tp": 100, "sl": 98,
                           "confidence": 0.9, "rationale": "x"})
    assert call.decision == "no_trade"
    assert any("flag" in g.lower() for g in call.gates_failed)


def test_account_unset_blocks(tmp_path):
    s = Store(str(tmp_path / "e3.db"))
    _fresh(s)
    s.set_setting("account_balance", "0")     # unset
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7})
    assert call.decision == "no_trade"
    assert any("account" in g.lower() for g in call.gates_failed)


def test_low_rr_blocks(tmp_path):
    s = Store(str(tmp_path / "e4.db"))
    _fresh(s)
    # tp barely above entry, sl far -> R:R < 1
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 67.45, "sl": 66.0,
                           "confidence": 0.7})
    assert call.decision == "no_trade"
    assert any("r:r" in g.lower() or "reward" in g.lower() for g in call.gates_failed)


def test_call_inputs_include_track_record(tmp_path):
    from glory_hype.db import Store
    from glory_hype.decision.engine import record_call
    s = Store(str(tmp_path / "tr.db"))
    _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.7, "rationale": "aligned"})
    assert "track_record" in call.inputs
    assert "win_rate" in call.inputs["track_record"]
