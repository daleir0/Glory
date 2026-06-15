from glory_hype.patterns.discover import discover_patterns

FEATS = ["price_slope", "oi_delta_pct", "vol_ratio", "atr_pct", "dist_from_high_20"]


def _vec(slope, oi, vol, atr, dh):
    return {"price_slope": slope, "oi_delta_pct": oi, "vol_ratio": vol,
            "atr_pct": atr, "dist_from_high_20": dh}


def test_discovers_two_clusters():
    # two clearly separated groups: quiet-coil vs loud-breakout
    coil = [_vec(0.02, 0.5, 0.4, 0.3, 3.0) for _ in range(15)]
    breakout = [_vec(0.6, 5.0, 3.0, 2.5, 0.5) for _ in range(15)]
    patterns = discover_patterns(coil + breakout, feature_keys=FEATS,
                                 min_occurrences=10, max_k=4)
    assert len(patterns) == 2
    for p in patterns:
        assert p["name"].startswith("disc_")
        assert p["n"] >= 10
        assert "centroid" in p


def test_too_few_samples_returns_empty():
    assert discover_patterns([_vec(0.1, 1, 1, 1, 1)] * 3, feature_keys=FEATS,
                             min_occurrences=10, max_k=4) == []
