from glory_hype.narrative.weights import RELIABILITY, weight_for


def test_weights_ordered_by_certainty():
    assert RELIABILITY["onchain"] == 1.0
    assert RELIABILITY["onchain"] > RELIABILITY["news"] > RELIABILITY["websearch"] > RELIABILITY["social"]


def test_weight_for_unknown_defaults_low():
    assert weight_for("mystery") == 0.3
    assert weight_for("news") == 0.7
