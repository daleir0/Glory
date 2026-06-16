"""Data-integrity flags for chart reads.

The core guardrail: a dropped chart's price must roughly agree with our live
Hyperliquid mark. A large divergence means the chart is a different instrument
(e.g. a same-ticker token on another venue) or stale — it must be flagged, not
silently fed into the calculator."""


def divergence_flags(read_price, live_mark, tol_pct: float = 5.0) -> list:
    """Return flag messages if read_price diverges from live_mark beyond tol_pct.
    Returns [] when inputs are missing/zero or within tolerance."""
    if not read_price or not live_mark:
        return []
    div_pct = abs(read_price - live_mark) / live_mark * 100
    if div_pct <= tol_pct:
        return []
    return [
        f"⚠️ Chart price {read_price} diverges {div_pct:.1f}% from live "
        f"Hyperliquid mark {live_mark} — likely a different instrument/venue or a "
        f"stale chart. Treat as unverified; not auto-filled into the calculator."
    ]
