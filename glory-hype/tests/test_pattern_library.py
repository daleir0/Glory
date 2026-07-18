from glory_hype.patterns.library import match_patterns, HAND_PATTERNS


def test_coil_expansion_matches():
    f = {"price_slope": 0.03, "vol_ratio": 0.5, "atr_pct": 0.4,
         "funding_compression": True, "oi_delta_pct": 1.0,
         "dist_from_high_20": 3.0, "funding_sign": 0}
    names = [m["name"] for m in match_patterns(f)]
    assert "COIL_EXPANSION" in names


def test_blowoff_top_matches():
    f = {"price_slope": 0.8, "vol_ratio": 3.0, "atr_pct": 2.5,
         "funding_compression": False, "oi_delta_pct": 5.0,
         "dist_from_high_20": 0.2, "funding_sign": 1}
    names = [m["name"] for m in match_patterns(f)]
    assert "BLOWOFF_TOP" in names


def test_mean_reversion_bounce_matches():
    f = {"price_slope": -0.3, "vol_ratio": 1.5, "atr_pct": 1.8,
         "funding_compression": False, "oi_delta_pct": -1.0,
         "dist_from_high_20": 8.0, "funding_sign": 1}
    names = [m["name"] for m in match_patterns(f)]
    assert "MEAN_REVERSION_BOUNCE" in names


def test_no_match_returns_empty():
    f = {"price_slope": 0.05, "vol_ratio": 1.0, "atr_pct": 1.0,
         "funding_compression": False, "oi_delta_pct": 0.0,
         "dist_from_high_20": 4.0, "funding_sign": 1}
    assert match_patterns(f) == []


def test_each_pattern_has_direction():
    for p in HAND_PATTERNS:
        assert p["direction"] in ("up", "down")
