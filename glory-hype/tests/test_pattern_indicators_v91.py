from glory_hype.patterns.indicators import features


def _c(o, h, l, c, v=1.0):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def test_funding_flip_and_slope():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": -0.0002, "open_interest": 1000.0},
           {"funding": 0.0003, "open_interest": 1000.0}]   # negative -> positive
    f = features(candles, ctx, vol_avg=1.0)
    assert f["funding_flip"] is True
    assert f["funding_slope"] > 0


def test_oi_surge_and_flow_imbalance():
    candles = [_c(100, 101, 99, 100)] * 4
    ctx = [{"funding": 0.0001, "open_interest": 1000.0},
           {"funding": 0.0001, "open_interest": 1100.0}]   # +10% OI
    trades = [{"side": "B", "ntl": 5000.0}, {"side": "B", "ntl": 5000.0},
              {"side": "A", "ntl": 1000.0}]                # buys dominate
    f = features(candles, ctx, trades_rows=trades, vol_avg=1.0, oi_baseline=1000.0)
    assert f["oi_surge"] is True
    assert f["flow_imbalance"] > 0       # buy-heavy
    assert f["oi_up_price_flat"] is True  # OI up, price flat


def test_features_backcompat_no_trades():
    # v9 callers pass no trades/baseline — must still work, new flow feats neutral
    f = features([_c(100, 101, 99, 100)], [{"funding": 0.0, "open_interest": 0.0}],
                 vol_avg=1.0)
    assert f["flow_imbalance"] == 0.0
    assert f["funding_flip"] is False
    assert "price_slope" in f
