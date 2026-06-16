from glory_hype.track.stats import compute_stats


def test_known_set():
    resolved = [
        {"status": "win", "r_multiple": 2.0},
        {"status": "win", "r_multiple": 2.0},
        {"status": "loss", "r_multiple": -1.0},
        {"status": "open", "r_multiple": None},
        {"status": "n/a", "r_multiple": None},
    ]
    s = compute_stats(resolved)
    assert s["n_closed"] == 3
    assert s["wins"] == 2 and s["losses"] == 1
    assert s["open_count"] == 1
    assert round(s["win_rate"], 4) == round(2 / 3, 4)
    assert s["avg_win_r"] == 2.0
    assert s["avg_loss_r"] == -1.0
    # expectancy = 2/3*2 + 1/3*(-1) = 1.0
    assert round(s["expectancy_r"], 4) == 1.0
    # profit factor = (2+2) / abs(-1) = 4.0
    assert s["profit_factor"] == 4.0


def test_empty_safe():
    s = compute_stats([])
    assert s["n_closed"] == 0
    assert s["win_rate"] is None
    assert s["expectancy_r"] is None
    assert s["profit_factor"] is None


def test_no_losses_profit_factor_none():
    s = compute_stats([{"status": "win", "r_multiple": 2.0}])
    assert s["profit_factor"] is None      # no losses -> undefined
    assert s["win_rate"] == 1.0
