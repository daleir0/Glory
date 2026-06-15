"""Pure regime classification from a feature vector."""

_TREND_SLOPE = 0.15     # % per bar to call a trend
_COIL_VOL = 0.7         # vol_ratio below this = quiet
_COIL_ATR = 0.6         # atr_pct below this = compressed


def classify(f: dict) -> str:
    slope = f.get("price_slope", 0.0)
    if slope >= _TREND_SLOPE:
        return "trending_up"
    if slope <= -_TREND_SLOPE:
        return "trending_down"
    # flat slope: coiling if quiet + compressed, else ranging
    if (f.get("vol_ratio", 1.0) < _COIL_VOL and f.get("atr_pct", 1.0) < _COIL_ATR
            and f.get("funding_compression", False)):
        return "coiling"
    return "ranging"
