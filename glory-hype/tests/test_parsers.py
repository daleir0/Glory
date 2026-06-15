from glory_hype.parsers import (
    parse_candle, parse_asset_ctx, parse_trade, is_large_trade,
)


def test_parse_candle():
    raw = {"t": 1780065720000, "T": 1780065779999, "s": "HYPE", "i": "1m",
           "o": "62.254", "c": "62.019", "h": "62.264", "l": "62.002",
           "v": "25485.75", "n": 720}
    c = parse_candle(raw)
    assert c == {"interval": "1m", "open_ts": 1780065720000, "close_ts": 1780065779999,
                 "o": 62.254, "h": 62.264, "l": 62.002, "c": 62.019,
                 "v": 25485.75, "n": 720}


def test_parse_asset_ctx():
    raw = {"funding": "0.0000125", "openInterest": "21950294.64", "prevDayPx": "56.964",
           "dayNtlVlm": "1048844881.51", "premium": "-0.0000321631", "oraclePx": "62.183",
           "markPx": "62.139", "midPx": "62.167", "impactPxs": ["62.164", "62.181"],
           "dayBaseVlm": "17099798.35"}
    ctx = parse_asset_ctx(raw)
    assert ctx["funding"] == 0.0000125
    assert ctx["open_interest"] == 21950294.64
    assert ctx["mark_px"] == 62.139
    assert ctx["oracle_px"] == 62.183
    assert ctx["mid_px"] == 62.167
    assert ctx["prev_day_px"] == 56.964
    assert ctx["day_ntl_vlm"] == 1048844881.51
    assert ctx["premium"] == -0.0000321631


def test_parse_trade():
    raw = {"coin": "HYPE", "side": "B", "px": "62.021", "sz": "161.23",
           "time": 1780065772043, "hash": "0xabc", "tid": 694120022159565,
           "users": ["0xaaa", "0xbbb"]}
    t = parse_trade(raw)
    assert t == {"ts": 1780065772043, "px": 62.021, "sz": 161.23,
                 "side": "B", "tid": 694120022159565,
                 "ntl": 62.021 * 161.23, "is_large": False}


def test_is_large_trade_threshold():
    assert is_large_trade(62.0, 1000.0) is True      # 62,000 >= 50,000
    assert is_large_trade(62.0, 100.0) is False       # 6,200 < 50,000
