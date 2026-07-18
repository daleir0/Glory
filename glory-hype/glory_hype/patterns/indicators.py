"""Pure feature extraction over a candle window + aligned ctx rows."""

import numpy as np

_FUNDING_EPS = 5e-6   # |funding| below this counts as compressed/near-zero


def features(candles: list, ctx_rows: list, trades_rows: list | None = None,
             vol_avg: float = 1.0, oi_baseline: float | None = None,
             funding_dist: dict | None = None) -> dict:
    if not candles:
        return {"price_slope": 0.0, "dist_from_high_20": 0.0, "dist_from_low_20": 0.0,
                "oi_delta_pct": 0.0, "funding_mean": 0.0, "funding_sign": 0,
                "funding_compression": True, "vol_ratio": 0.0, "atr_pct": 0.0,
                "range_pct": 0.0, "body_ratio": 0.0,
                "funding_flip": False, "funding_slope": 0.0, "funding_extreme": 0.0,
                "oi_surge": False, "oi_drop": False, "oi_accel": 0.0,
                "flow_imbalance": 0.0, "flow_spike": 0.0,
                "oi_up_price_flat": False, "funding_div": False,
                }
    closes = np.array([c["c"] for c in candles], dtype=float)
    highs = np.array([c["h"] for c in candles], dtype=float)
    lows = np.array([c["l"] for c in candles], dtype=float)
    opens = np.array([c["o"] for c in candles], dtype=float)
    vols = np.array([c["v"] for c in candles], dtype=float)
    last = closes[-1]

    # price slope: linreg of closes, normalized to % per bar
    x = np.arange(len(closes))
    slope = float(np.polyfit(x, closes, 1)[0]) / last * 100 if len(closes) > 1 else 0.0

    hi, lo = float(highs.max()), float(lows.min())
    dist_high = (hi - last) / last * 100
    dist_low = (last - lo) / last * 100

    funding = [r.get("funding", 0.0) for r in ctx_rows] or [0.0]
    fmean = float(np.mean(funding))
    fsign = 0 if abs(fmean) < _FUNDING_EPS else (1 if fmean > 0 else -1)

    ois = [r.get("open_interest", 0.0) for r in ctx_rows if r.get("open_interest")]
    oi_delta = ((ois[-1] - ois[0]) / ois[0] * 100) if len(ois) >= 2 and ois[0] else 0.0

    atr = float(np.mean(highs - lows)) / last * 100
    rng = (hi - lo) / last * 100
    body = float(np.mean(np.abs(closes - opens)) / np.mean(np.maximum(highs - lows, 1e-9)))

    # funding dynamics
    fund_series = [r.get("funding", 0.0) for r in ctx_rows] or [0.0]
    funding_flip = (min(fund_series) < 0 < max(fund_series))
    if len(fund_series) > 1:
        fx = np.arange(len(fund_series))
        funding_slope = float(np.polyfit(fx, fund_series, 1)[0])
    else:
        funding_slope = 0.0
    if funding_dist and funding_dist.get("std"):
        funding_extreme = (fmean - funding_dist.get("mean", 0.0)) / funding_dist["std"]
    else:
        funding_extreme = 0.0

    # OI dynamics
    oi_surge = oi_delta >= 5.0
    oi_drop = oi_delta <= -5.0
    oi_accel = 0.0
    if len(ois) >= 3 and ois[0]:
        d1 = ois[-1] - ois[-2]
        d0 = ois[-2] - ois[0]
        oi_accel = (d1 - d0) / ois[0] * 100

    # large-trade flow
    flow_imbalance, flow_spike = 0.0, 0.0
    if trades_rows:
        buys = sum(t["ntl"] for t in trades_rows if t.get("side") == "B")
        sells = sum(t["ntl"] for t in trades_rows if t.get("side") == "A")
        total = buys + sells
        if total:
            flow_imbalance = (buys - sells) / total
        if oi_baseline:   # crude baseline reuse; spike vs notional baseline
            flow_spike = total / max(oi_baseline, 1e-9)

    oi_up_price_flat = (oi_delta > 2.0 and abs(slope) < 0.1)
    funding_div = ((funding_slope > 0) != (slope > 0)) and abs(slope) > 0.05

    return {
        "price_slope": slope,
        "dist_from_high_20": dist_high,
        "dist_from_low_20": dist_low,
        "oi_delta_pct": round(oi_delta, 4),
        "funding_mean": fmean,
        "funding_sign": fsign,
        "funding_compression": abs(fmean) < _FUNDING_EPS,
        "vol_ratio": float(vols.mean() / vol_avg) if vol_avg else 0.0,
        "atr_pct": round(atr, 4),
        "range_pct": round(rng, 4),
        "body_ratio": round(body, 4),
        "funding_flip": bool(funding_flip),
        "funding_slope": round(funding_slope, 8),
        "funding_extreme": round(funding_extreme, 4),
        "oi_surge": bool(oi_surge), "oi_drop": bool(oi_drop),
        "oi_accel": round(oi_accel, 4),
        "flow_imbalance": round(flow_imbalance, 4),
        "flow_spike": round(flow_spike, 6),
        "oi_up_price_flat": bool(oi_up_price_flat),
        "funding_div": bool(funding_div),
    }
