from glory_hype import config


def test_intervals_all_have_ms():
    for iv in config.INTERVALS:
        assert iv in config.INTERVAL_MS
        assert config.INTERVAL_MS[iv] > 0


def test_coin_is_hype():
    assert config.COIN == "HYPE"
