from glory_hype.patterns.regime import classify


def test_trending_up():
    assert classify({"price_slope": 0.5, "vol_ratio": 1.2, "atr_pct": 1.5,
                     "funding_compression": False}) == "trending_up"


def test_trending_down():
    assert classify({"price_slope": -0.5, "vol_ratio": 1.2, "atr_pct": 1.5,
                     "funding_compression": False}) == "trending_down"


def test_coiling():
    # flat slope + low vol + funding compressed = coil before expansion
    assert classify({"price_slope": 0.02, "vol_ratio": 0.5, "atr_pct": 0.4,
                     "funding_compression": True}) == "coiling"


def test_ranging():
    assert classify({"price_slope": 0.05, "vol_ratio": 1.0, "atr_pct": 1.2,
                     "funding_compression": False}) == "ranging"
