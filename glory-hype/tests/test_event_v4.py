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


def test_event_context_in_inputs(tmp_path):
    s = Store(str(tmp_path / "v.db"))
    now = _fresh(s)
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    assert "event_context" in call.inputs


def test_event_within_48h_adds_caution(tmp_path):
    s = Store(str(tmp_path / "v2.db"))
    now = _fresh(s)
    # an unlock 24h out
    s.insert_event({"date_ms": now + 24 * 3600_000, "type": "unlock",
                    "label": "unlock soon", "magnitude_pct": 2.5, "magnitude_usd": 6.8e8,
                    "source_url": "", "notes": ""})
    call = record_call(s, {"decision": "long", "entry": 67.4, "tp": 68.2, "sl": 66.7,
                           "confidence": 0.6, "rationale": "x"})
    ec = call.inputs["event_context"]
    assert ec["caution"] is True
    assert "unlock" in ec["nearest"]["type"]
