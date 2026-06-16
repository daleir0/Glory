from glory_hype.patterns.sweep import config_grid, score_config
from glory_hype import config


def test_config_grid_size():
    grid = config_grid()
    assert len(grid) == len(config.SWEEP_THRESHOLDS) * len(config.SWEEP_HORIZONS)
    assert (2.0, 6) in grid


def test_score_config_counts_directional_wins():
    # member rows: (features, future_candles). Up move of 5% within horizon.
    def fut(up):
        base = 100.0
        peak = base * (1.05 if up else 0.95)
        return [{"open_ts": 1, "c": base, "h": max(base, peak), "l": min(base, peak)}]
    members = [({"x": 1}, fut(True)), ({"x": 1}, fut(True)), ({"x": 1}, fut(False))]
    res = score_config(members, start_closes=[100.0, 100.0, 100.0],
                       direction="up", threshold=4.0, horizon=6)
    assert res["n"] == 3
    assert res["wins"] == 2       # two up-moves matched 'up'
