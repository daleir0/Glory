import pytest
from glory_hype.calc import compute_trade


def test_margin_mode_long():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 95.0,
                       "direction": "long", "leverage": 10, "margin": 500.0})
    assert r["position_notional"] == 5000.0          # 500 * 10
    assert r["position_coins"] == 50.0               # 5000 / 100
    assert r["margin"] == 500.0
    assert r["pnl_at_tp"] == 500.0                    # 50 * (110-100)
    assert r["pnl_at_sl"] == -250.0                   # 50 * (95-100)
    assert r["roi_tp"] == 1.0                          # 500/500
    assert r["roi_sl"] == -0.5
    assert r["rr"] == 2.0                              # |110-100| / |100-95|
    assert round(r["liq_price"], 2) == 90.0            # 100*(1-1/10)


def test_position_mode_short():
    r = compute_trade({"mode": "position", "entry": 100.0, "tp": 90.0, "sl": 104.0,
                       "direction": "short", "leverage": 5,
                       "position_notional": 5000.0})
    assert r["margin"] == 1000.0                       # 5000/5
    assert r["position_coins"] == 50.0
    assert r["pnl_at_tp"] == 500.0                     # short: 50*(100-90)
    assert r["pnl_at_sl"] == -200.0                    # 50*(100-104)
    assert r["rr"] == 2.5                              # |90-100| / |100-104|
    assert round(r["liq_price"], 2) == 120.0           # 100*(1+1/5)


def test_risk_pct_mode_sizes_to_risk():
    # risk 2% of 10000 = $200 loss at SL; entry-sl distance = 5 -> coins = 40
    r = compute_trade({"mode": "risk_pct", "entry": 100.0, "tp": 115.0, "sl": 95.0,
                       "direction": "long", "leverage": 10,
                       "account": 10000.0, "risk_pct": 0.02})
    assert r["position_coins"] == 40.0                 # 200 / 5
    assert r["position_notional"] == 4000.0            # 40 * 100
    assert r["margin"] == 400.0                         # 4000 / 10
    assert round(r["pnl_at_sl"], 2) == -200.0           # exactly the risk
    assert r["pnl_at_tp"] == 600.0                       # 40 * 15


def test_rr_none_when_no_risk_distance():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 110.0, "sl": 100.0,
                       "direction": "long", "leverage": 2, "margin": 100.0})
    assert r["rr"] is None


def test_suggestion_low_rr():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 102.0, "sl": 95.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("smaller than risk" in s.lower() for s in r["suggestions"])


def test_suggestion_healthy_rr():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 120.0, "sl": 95.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("healthy r:r" in s.lower() for s in r["suggestions"])


def test_suggestion_sl_beyond_liquidation():
    # long, leverage 10 -> liq ~90; sl at 88 is beyond liq
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 130.0, "sl": 88.0,
                       "direction": "long", "leverage": 10, "margin": 100.0})
    assert any("liquidation" in s.lower() for s in r["suggestions"])


def test_suggestion_inverted_tp():
    r = compute_trade({"mode": "margin", "entry": 100.0, "tp": 95.0, "sl": 90.0,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    assert any("wrong side" in s.lower() for s in r["suggestions"])


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        compute_trade({"mode": "margin", "entry": 0, "tp": 1, "sl": 1,
                       "direction": "long", "leverage": 5, "margin": 100.0})
    with pytest.raises(ValueError):
        compute_trade({"mode": "margin", "entry": 100, "tp": 110, "sl": 95,
                       "direction": "long", "leverage": 0.5, "margin": 100.0})
    with pytest.raises(ValueError):
        compute_trade({"mode": "risk_pct", "entry": 100, "tp": 110, "sl": 100,
                       "direction": "long", "leverage": 5,
                       "account": 1000, "risk_pct": 0.02})  # zero risk distance
