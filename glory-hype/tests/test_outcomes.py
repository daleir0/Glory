from glory_hype.track.outcomes import resolve_outcome


def _candle(open_ts, h, l):
    return {"interval": "1m", "open_ts": open_ts, "close_ts": open_ts + 59999,
            "o": l, "h": h, "l": l, "c": h, "v": 1.0, "n": 1}


def _call(decision="long", entry=100.0, tp=110.0, sl=95.0, ts=0):
    return {"decision": decision, "entry": entry, "tp": tp, "sl": sl,
            "generated_at": ts}


def test_long_win():
    candles = [_candle(1, 102, 99), _candle(2, 111, 108)]  # 2nd hits tp 110
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "win"
    assert o["exit_price"] == 110.0
    assert o["r_multiple"] == 2.0          # reward 10 / risk 5
    assert o["ambiguous"] is False


def test_long_loss():
    candles = [_candle(1, 103, 96), _candle(2, 104, 94)]   # 2nd hits sl 95
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "loss"
    assert o["exit_price"] == 95.0
    assert o["r_multiple"] == -1.0


def test_long_open():
    candles = [_candle(1, 103, 97), _candle(2, 104, 98)]   # neither tp nor sl
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "open"
    assert o["r_multiple"] is None


def test_long_straddle_is_loss():
    candles = [_candle(1, 111, 94)]   # one candle spans both tp and sl
    o = resolve_outcome(_call(), candles)
    assert o["status"] == "loss"
    assert o["ambiguous"] is True


def test_short_win():
    # short entry 100 tp 90 sl 104; candle low 89 hits tp
    candles = [_candle(1, 101, 89)]
    o = resolve_outcome(_call(decision="short", tp=90.0, sl=104.0), candles)
    assert o["status"] == "win"
    assert o["r_multiple"] == 2.5         # reward 10 / risk 4


def test_short_loss():
    candles = [_candle(1, 105, 99)]       # high 105 hits sl 104
    o = resolve_outcome(_call(decision="short", tp=90.0, sl=104.0), candles)
    assert o["status"] == "loss"


def test_no_trade_is_na():
    o = resolve_outcome({"decision": "no_trade", "generated_at": 0}, [])
    assert o["status"] == "n/a"


def test_missing_levels_is_na():
    o = resolve_outcome({"decision": "long", "entry": 100, "tp": None,
                         "sl": 95, "generated_at": 0}, [_candle(1, 200, 50)])
    assert o["status"] == "n/a"


# --- entry-fill bug fix: a call only resolves if the entry was actually touched ---

def test_long_unfilled_when_price_never_reaches_entry():
    # long limit at 100, but price gapped up and never came down to 100 -> unfilled
    candles = [_candle(1, 105, 101), _candle(2, 112, 108)]  # lows 101,108 both > entry 100
    o = resolve_outcome(_call(entry=100.0, tp=110.0, sl=95.0), candles)
    assert o["status"] == "unfilled"
    assert o["r_multiple"] is None


def test_long_fills_then_wins():
    # price dips to 100 (fills), then runs to TP 110
    candles = [_candle(1, 101, 99), _candle(2, 111, 105)]  # candle1 low 99<=100 fills
    o = resolve_outcome(_call(entry=100.0, tp=110.0, sl=95.0), candles)
    assert o["status"] == "win"


def test_long_fills_then_loses():
    candles = [_candle(1, 101, 100), _candle(2, 101, 94)]  # fills c1, sl 95 hit c2
    o = resolve_outcome(_call(entry=100.0, tp=110.0, sl=95.0), candles)
    assert o["status"] == "loss"


def test_short_unfilled_when_price_never_reaches_entry():
    # short limit at 100, price never rose to 100 -> unfilled
    candles = [_candle(1, 98, 95), _candle(2, 97, 90)]  # highs 98,97 both < entry 100
    o = resolve_outcome(_call(decision="short", entry=100.0, tp=90.0, sl=104.0), candles)
    assert o["status"] == "unfilled"
