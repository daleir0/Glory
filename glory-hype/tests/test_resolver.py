from glory_hype.db import Store


def _candle(ts, h, l):
    return {"interval": "1m", "open_ts": ts, "close_ts": ts + 59999,
            "o": l, "h": h, "l": l, "c": h, "v": 1.0, "n": 1}


def test_store_status_open_and_candles_since(tmp_path):
    s = Store(str(tmp_path / "r.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.insert_trade_call({"generated_at": 1100, "decision": "no_trade",
                         "gates_failed": ["x"]})
    opens = s.open_trade_calls()
    assert len(opens) == 1 and opens[0]["decision"] == "long"   # no_trade excluded
    for c in [_candle(900, 1, 1), _candle(1500, 111, 108), _candle(2000, 112, 109)]:
        s.insert_candle(c)
    later = s.candles_since("1m", 1000)
    assert [c["open_ts"] for c in later] == [1500, 2000]         # strictly after ts


def test_store_update_outcome(tmp_path):
    s = Store(str(tmp_path / "r2.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    s.update_call_outcome(1000, {"status": "win", "exit_price": 110.0,
                                 "r_multiple": 2.0, "ambiguous": False})
    s.set_setting  # ensure store import path ok
    latest = s.latest_trade_call()
    assert latest["status"] == "win"
    assert latest["r_multiple"] == 2.0
    assert latest["exit_price"] == 110.0
    assert s.open_trade_calls() == []        # no longer open


def test_resolve_open_calls_marks_win_and_idempotent(tmp_path):
    from glory_hype.track.resolver import resolve_open_calls, track_summary
    s = Store(str(tmp_path / "r3.db"))
    s.insert_trade_call({"generated_at": 1000, "decision": "long", "entry": 100,
                         "tp": 110, "sl": 95})
    for c in [_candle(1500, 105, 99), _candle(2000, 111, 108)]:  # 2nd hits tp
        s.insert_candle(c)
    stats = resolve_open_calls(s)
    assert stats["wins"] == 1 and stats["n_closed"] == 1
    assert s.latest_trade_call()["status"] == "win"
    assert s.open_trade_calls() == []          # resolved
    # idempotent: re-run changes nothing
    stats2 = resolve_open_calls(s)
    assert stats2["wins"] == 1 and stats2["n_closed"] == 1
    summ = track_summary(s)
    assert summ["win_rate"] == 1.0
