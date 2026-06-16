import math
from glory_hype.patterns.stats import wilson_ci, forward_outcome


def test_wilson_ci_basic():
    lo, hi = wilson_ci(wins=8, n=10)
    assert 0.4 < lo < 0.6      # 80% over 10 -> wide CI, lower bound ~0.49
    assert hi > 0.9
    lo2, _ = wilson_ci(wins=35, n=50)
    assert lo2 > lo            # more samples at 70% -> higher lower bound than 8/10


def test_wilson_ci_zero_n():
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_forward_outcome_up():
    # candles after t0: price runs from 100 to 105 within window -> +5%, 'up'
    candles = [{"open_ts": 10, "c": 100, "h": 100, "l": 100},
               {"open_ts": 20, "c": 103, "h": 103, "l": 100},
               {"open_ts": 30, "c": 105, "h": 105, "l": 102}]
    o = forward_outcome(start_close=100.0, future=candles, threshold_pct=4.0)
    assert o["direction"] == "up"
    assert round(o["move_pct"], 1) == 5.0
    assert o["hit"] is True


def test_forward_outcome_none():
    candles = [{"open_ts": 10, "c": 100, "h": 101, "l": 99},
               {"open_ts": 20, "c": 101, "h": 102, "l": 100}]
    o = forward_outcome(start_close=100.0, future=candles, threshold_pct=4.0)
    assert o["hit"] is False
    assert o["direction"] == "none"
