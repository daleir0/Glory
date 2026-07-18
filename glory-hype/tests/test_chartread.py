from glory_hype.chart.chartread import ChartRead, parse_chart_read


def test_parse_full():
    data = {
        "timeframe": "1h", "exchange_pair": "Hyperliquid HYPE-USD",
        "price_range_low": 60.0, "price_range_high": 67.0,
        "current_price": 65.6, "swing_high": 66.84, "swing_low": 61.9,
        "trend": "up", "support_levels": [64.0, 62.0],
        "resistance_levels": [66.8], "patterns": ["ascending triangle"],
        "signals": ["bullish engulfing"], "indicators": {"rsi": 68.0},
        "position": {"side": "long", "entry": 63.0}, "orders": ["TP 70"],
        "annotations": ["trendline from 58"], "visible_text": ["HYPE", "Perp"],
        "notes": "uptrend, extended",
    }
    c = parse_chart_read(data, ts=1000, image_path="charts/x.png")
    assert c.timeframe == "1h"
    assert c.current_price == 65.6
    assert c.trend == "up"
    assert c.support_levels == [64.0, 62.0]
    assert c.indicators["rsi"] == 68.0
    assert c.position["side"] == "long"
    assert c.image_path == "charts/x.png"
    assert c.ts == 1000
    assert c.raw == data


def test_parse_partial_defaults():
    c = parse_chart_read({"current_price": 65.0}, ts=5, image_path=None)
    assert c.timeframe == "unknown"
    assert c.trend == "unknown"
    assert c.support_levels == []
    assert c.resistance_levels == []
    assert c.patterns == []
    assert c.indicators == {}
    assert c.position is None
    assert c.current_price == 65.0
    assert c.swing_high is None


def test_parse_drops_non_numeric_levels():
    c = parse_chart_read(
        {"support_levels": [64.0, "n/a", None, 62.5], "resistance_levels": "67"},
        ts=1, image_path=None)
    assert c.support_levels == [64.0, 62.5]
    assert c.resistance_levels == []   # non-list -> empty


def test_parse_garbage_is_safe():
    c = parse_chart_read({"trend": 123, "current_price": "not-a-number"},
                         ts=9, image_path=None)
    assert c.trend == "unknown"        # non-str/invalid -> unknown
    assert c.current_price is None     # uncoercible -> None
    assert isinstance(c.to_dict(), dict)


def test_to_dict_roundtrips_collections():
    c = parse_chart_read({"patterns": ["flag"], "indicators": {"rsi": 70}},
                         ts=2, image_path=None)
    d = c.to_dict()
    assert d["patterns"] == ["flag"]
    assert d["indicators"] == {"rsi": 70}
    assert d["ts"] == 2
