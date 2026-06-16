from glory_hype.patterns.indicators import features


def _c(o, h, l, c, v=1.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def test_features_uptrend():
    candles = [_c(100, 101, 99, 100), _c(100, 103, 100, 102),
               _c(102, 106, 101, 105), _c(105, 109, 104, 108)]
    ctx = [{"funding": 0.0001, "open_interest": 1000.0},
           {"funding": 0.0001, "open_interest": 1100.0}]
    f = features(candles, ctx, vol_avg=1.0)
    assert f["price_slope"] > 0                 # rising closes
    assert f["oi_delta_pct"] == 10.0            # 1000 -> 1100
    assert f["funding_sign"] == 1
    assert f["dist_from_low_20"] > 0
    assert "vol_ratio" in f and "atr_pct" in f


def test_features_funding_compression():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": 0.000001, "open_interest": 1000.0},
           {"funding": -0.000001, "open_interest": 1000.0}]
    f = features(candles, ctx, vol_avg=1.0)
    assert f["funding_compression"] is True     # |funding| ~ 0
    assert f["funding_sign"] == 0


def test_features_empty_safe():
    f = features([], [], vol_avg=1.0)
    assert f["price_slope"] == 0.0
    assert f["oi_delta_pct"] == 0.0
