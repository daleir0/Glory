"""Pure event-study: window behavior around a catalyst + small-N composite.

Descriptive only — no statistical inference. Composite reports median + N honestly."""

import statistics


def study_event(event: dict, candles: list, ctx_rows: list, window_days: int) -> dict:
    """candles: 1h candles (ascending) already sliced near the event (or full — we filter).
    Returns pre/post/trough/peak % relative to the event, and the normalized path."""
    ev = event["date_ms"]
    half = window_days * 86400_000
    win = [c for c in candles if ev - half <= c["open_ts"] <= ev + half]
    if not win:
        return {"pre_pct": None, "post_pct": None, "trough_pct": None,
                "peak_pct": None, "n_candles": 0, "path": []}
    # event close = the candle closest to ev
    ev_candle = min(win, key=lambda c: abs(c["open_ts"] - ev))
    p0 = win[0]["c"]
    pe = ev_candle["c"]
    pend = win[-1]["c"]
    pre_pct = (pe - p0) / p0 * 100
    post_pct = (pend - pe) / pe * 100
    lows = [c["l"] for c in win]
    highs = [c["h"] for c in win]
    trough_pct = (min(lows) - pe) / pe * 100
    peak_pct = (max(highs) - pe) / pe * 100
    path = [round((c["c"] - pe) / pe * 100 + 100, 3) for c in win]   # normalized to 100 at event
    return {"pre_pct": pre_pct, "post_pct": post_pct, "trough_pct": trough_pct,
            "peak_pct": peak_pct, "n_candles": len(win), "path": path}


def _median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None


def composite(studies: list, type_: str) -> dict:
    usable = [s for s in studies if s.get("pre_pct") is not None]
    n = len(usable)
    if n == 0:
        return {"type": type_, "n": 0, "median_pre": None, "median_post": None,
                "median_trough": None, "median_peak": None, "spread": {},
                "confidence_label": "no studiable history"}
    label = (f"small-sample composite (N={n})" if n >= 3
             else f"insufficient history — directional only (N={n})")
    pres = [s["pre_pct"] for s in usable]
    posts = [s["post_pct"] for s in usable]
    return {"type": type_, "n": n,
            "median_pre": _median(pres), "median_post": _median(posts),
            "median_trough": _median([s["trough_pct"] for s in usable]),
            "median_peak": _median([s["peak_pct"] for s in usable]),
            "spread": {"pre_min": min(pres), "pre_max": max(pres),
                       "post_min": min(posts), "post_max": max(posts)},
            "confidence_label": label}
