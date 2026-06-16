from glory_hype.gaps import find_candle_gaps


def test_no_gaps():
    assert find_candle_gaps([0, 60000, 120000], 60000) == []


def test_one_missing_candle():
    # missing 60000 between 0 and 120000
    assert find_candle_gaps([0, 120000], 60000) == [60000]


def test_multiple_missing():
    assert find_candle_gaps([0, 240000], 60000) == [60000, 120000, 180000]


def test_empty_and_single():
    assert find_candle_gaps([], 60000) == []
    assert find_candle_gaps([1000], 60000) == []
