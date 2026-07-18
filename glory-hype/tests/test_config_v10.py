from glory_hype import config


def test_assets_registry_exists():
    assert hasattr(config, "ASSETS")
    assert "hype" in config.ASSETS
    assert config.ASSETS["hype"].coin == "HYPE"
    assert config.ASSETS["hype"].db == "hype.db"
    assert config.ASSETS["near"].coin == "NEAR"
    assert config.ASSETS["icp"].coin == "ICP"
    assert config.ASSETS["vvv"].coin == "VVV"


def test_min_rr_raised():
    assert config.MIN_RR == 1.5


def test_narrative_stale_12h():
    assert config.NARRATIVE_STALE_MS == 12 * 60 * 60 * 1000


def test_lm_studio_config():
    assert config.LM_STUDIO_URL == "http://169.254.83.107:1234"
    assert config.LM_STUDIO_MODEL == "90f9618340396838ee7ff5b0ba2da27da62953d3"
