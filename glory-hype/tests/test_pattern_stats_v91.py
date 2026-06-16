from glory_hype.patterns.stats import binomial_p, benjamini_hochberg, forward_outcome


def test_binomial_p_strong():
    # 18 wins of 20 fair coin flips -> very unlikely under p=0.5
    assert binomial_p(18, 20) < 0.001


def test_binomial_p_chance():
    # 11 of 20 -> not significant
    assert binomial_p(11, 20) > 0.2


def test_binomial_p_edges():
    assert binomial_p(0, 0) == 1.0
    assert 0.0 <= binomial_p(10, 10) <= 1.0


def test_benjamini_hochberg_picks_significant():
    pvals = [0.001, 0.008, 0.04, 0.2, 0.7]
    sig = benjamini_hochberg(pvals, q=0.05)
    # the smallest few survive, the large ones do not
    assert sig[0] is True and sig[1] is True
    assert sig[3] is False and sig[4] is False


def test_benjamini_hochberg_all_null():
    assert benjamini_hochberg([0.6, 0.7, 0.9], q=0.05) == [False, False, False]


def test_forward_outcome_horizon_limits_lookahead():
    # move only happens at candle 5; horizon=3 must NOT see it
    future = [{"open_ts": i, "c": 100, "h": 100.5, "l": 99.5} for i in range(4)]
    future.append({"open_ts": 5, "c": 100, "h": 110, "l": 100})  # +10% at index 4
    near = forward_outcome(100.0, future, threshold_pct=4.0, horizon=3)
    assert near["hit"] is False
    far = forward_outcome(100.0, future, threshold_pct=4.0, horizon=10)
    assert far["hit"] is True
