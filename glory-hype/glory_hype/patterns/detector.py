"""Live pattern signal: featurize the current window, match stable patterns."""

import json

from glory_hype import config
from glory_hype.patterns.indicators import features
from glory_hype.patterns.library import match_patterns
from glory_hype.patterns.regime import classify

WINDOW = 12


def current_signal(store) -> dict:
    candles = store.recent_candles("1h", WINDOW)
    if len(candles) < 2:
        return {"regime": "unknown", "features": {}, "matches": []}
    with store._lock:
        ctx = [dict(r) for r in store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (candles[0]["open_ts"], candles[-1]["close_ts"])).fetchall()]
        trades = [dict(r) for r in store.conn.execute(
            "SELECT side, ntl FROM trades WHERE is_large=1 AND ts BETWEEN ? AND ? ORDER BY ts",
            (candles[0]["open_ts"], candles[-1]["close_ts"])).fetchall()]
    vols = [c["v"] for c in store.recent_candles("1h", 14 * 24)]
    vol_avg = (sum(vols) / len(vols)) if vols else 1.0
    f = features(candles, ctx, trades_rows=trades, vol_avg=vol_avg)
    regime = classify(f)

    stable = {s["pattern_name"]: s for s in store.stable_pattern_stats(config.PATTERN_SIGNAL_CONF)}
    matches = []
    for m in match_patterns(f):
        st = stable.get(m["name"])
        if st:
            matches.append({"pattern_name": m["name"], "direction": st["direction"],
                            "confidence": round(st["win_lo_test"], 4),
                            "avg_move_pct": st["avg_move_pct"], "source": st["source"]})
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return {"regime": regime, "features": f, "matches": matches}
