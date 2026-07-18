"""Hand-coded named patterns. Domain knowledge proposes; data (backtest) decides."""


def _coil_expansion(f):
    return (abs(f["price_slope"]) < 0.1 and f["vol_ratio"] < 0.7
            and f["atr_pct"] < 0.6 and f["funding_compression"])


def _etf_catalyst_breakout(f):
    return (f["price_slope"] > 0.2 and f["oi_delta_pct"] > 3.0
            and f["vol_ratio"] > 1.5)


def _unlock_fear_dump(f):
    return (f["price_slope"] < -0.1 and f["oi_delta_pct"] < -1.0
            and f["funding_sign"] <= 0)


def _blowoff_top(f):
    return (f["price_slope"] > 0.5 and f["vol_ratio"] > 2.0
            and f["dist_from_high_20"] < 1.0)


def _mean_reversion_bounce(f):
    return (f["dist_from_high_20"] >= 7.0 and f["funding_sign"] >= 1
            and f["oi_delta_pct"] > -3.0)


def _capitulation_low(f):
    return (f["price_slope"] < -0.4 and f["vol_ratio"] > 2.0
            and f["funding_sign"] < 0)


HAND_PATTERNS = [
    {"name": "COIL_EXPANSION", "predicate": _coil_expansion, "direction": "up"},
    {"name": "ETF_CATALYST_BREAKOUT", "predicate": _etf_catalyst_breakout, "direction": "up"},
    {"name": "UNLOCK_FEAR_DUMP", "predicate": _unlock_fear_dump, "direction": "down"},
    {"name": "BLOWOFF_TOP", "predicate": _blowoff_top, "direction": "down"},
    {"name": "MEAN_REVERSION_BOUNCE", "predicate": _mean_reversion_bounce, "direction": "up"},
    {"name": "CAPITULATION_LOW", "predicate": _capitulation_low, "direction": "up"},
]


def match_patterns(f: dict) -> list:
    out = []
    for p in HAND_PATTERNS:
        try:
            if p["predicate"](f):
                out.append({"name": p["name"], "source": "hand", "direction": p["direction"]})
        except KeyError:
            continue
    return out
