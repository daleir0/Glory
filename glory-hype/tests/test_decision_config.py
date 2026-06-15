from glory_hype import config


def test_decision_thresholds_present():
    assert config.MIN_RR == 1.5
    assert config.NARRATIVE_STALE_MS == 12 * 60 * 60 * 1000
    assert config.CTX_STALE_MS == 5 * 60 * 1000
    assert config.DEFAULT_RISK_PCT == 0.01
    assert config.DEFAULT_LEVERAGE == 10
