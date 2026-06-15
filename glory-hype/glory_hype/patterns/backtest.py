"""Walk history with richer features, a config sweep, 3-way split, and BH-FDR gating."""

import json
import time

from glory_hype import config
from glory_hype.patterns import discover as disc
from glory_hype.patterns.indicators import features
from glory_hype.patterns.library import HAND_PATTERNS, match_patterns
from glory_hype.patterns.regime import classify
from glory_hype.patterns.stats import benjamini_hochberg, binomial_p, wilson_ci
from glory_hype.patterns.sweep import config_grid, score_config

WINDOW = 12
_FEATS = ["price_slope", "oi_delta_pct", "vol_ratio", "atr_pct", "dist_from_high_20",
          "flow_imbalance", "funding_slope", "oi_accel"]


def _ctx_for(store, a, b):
    with store._lock:
        rows = store.conn.execute(
            "SELECT funding, open_interest FROM market_ctx WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (a, b)).fetchall()
    return [dict(r) for r in rows]


def _trades_for(store, a, b):
    with store._lock:
        rows = store.conn.execute(
            "SELECT side, ntl FROM trades WHERE is_large=1 AND ts BETWEEN ? AND ? ORDER BY ts",
            (a, b)).fetchall()
    return [dict(r) for r in rows]


def run_backtest(store) -> dict:
    candles = store.recent_candles("1h", 100000)
    max_h = max(config.SWEEP_HORIZONS)
    if len(candles) < WINDOW + max_h + 40:
        return {"events_detected": 0, "patterns": 0}
    vols = [c["v"] for c in candles]
    vol_avg = (sum(vols) / len(vols)) or 1.0

    n = len(candles)
    i_train = int(n * config.SPLIT_TRAIN)
    i_test = int(n * (config.SPLIT_TRAIN + config.SPLIT_TEST))

    # build per-bar feature rows with aligned future candles
    rows = []   # dict: idx, split, features, regime, start_close, future
    for i in range(WINDOW, n - max_h):
        win = candles[i - WINDOW:i]
        ctx = _ctx_for(store, win[0]["open_ts"], win[-1]["close_ts"])
        trades = _trades_for(store, win[0]["open_ts"], win[-1]["close_ts"])
        f = features(win, ctx, trades_rows=trades, vol_avg=vol_avg)
        reg = classify(f)
        store.insert_regime({"ts": candles[i]["open_ts"], "timeframe": "1h",
                             "label": reg, "features_json": json.dumps(f)})
        split = "train" if i < i_train else ("test" if i < i_test else "holdout")
        rows.append({"idx": i, "split": split, "f": f, "regime": reg,
                     "start_close": candles[i - 1]["c"], "future": candles[i:i + max_h]})

    # candidate hypotheses: (pattern_name, source, direction, members_by_split)
    hypotheses = []

    def members_for(predicate_name):
        sel = {"train": [], "test": [], "holdout": []}
        for r in rows:
            if any(m["name"] == predicate_name for m in match_patterns(r["f"])):
                sel[r["split"]].append(r)
        return sel

    for p in HAND_PATTERNS:
        sel = members_for(p["name"])
        hypotheses.append({"name": p["name"], "source": "hand",
                           "direction": p["direction"], "sel": sel})

    # discovered patterns: cluster TRAIN move-event features, assign test/holdout by centroid
    train_event_feats = [r["f"] for r in rows
                         if r["split"] == "train"
                         and _quick_move(r["start_close"], r["future"])]
    discovered = disc.discover_patterns(train_event_feats, _FEATS,
                                        config.PATTERN_MIN_OCCURRENCES)
    now = int(time.time() * 1000)
    for d in discovered:
        store.insert_discovered_pattern({"name": d["name"],
            "centroid_json": json.dumps(d["centroid"]),
            "dominant_features_json": json.dumps(d["dominant_features"]),
            "created_at": now})
        sel = {"train": [], "test": [], "holdout": []}
        # train members are the cluster's own; test/holdout via centroid assignment
        scaler = d["scaler"]
        for split in ("train", "test", "holdout"):
            vs = [r for r in rows if r["split"] == split]
            labs = disc.assign_to_centroids([r["f"] for r in vs], [d["centroid"]],
                                            _FEATS, scaler, config.OOS_MAX_DIST)
            sel[split] = [vs[k] for k, lab in enumerate(labs) if lab == 0]
        # direction = majority forward direction of train members (default up)
        ups = sum(1 for r in sel["train"]
                  if _move_dir(r["start_close"], r["future"]) == "up")
        direction = "up" if ups >= len(sel["train"]) / 2 else "down"
        hypotheses.append({"name": d["name"], "source": "disc",
                           "direction": direction, "sel": sel})

    # sweep each hypothesis over configs on TEST; pick best; binomial p
    candidates = []
    for h in hypotheses:
        test_m = h["sel"]["test"]
        if len(test_m) < 5:
            continue
        best = None
        for (thr, hor) in config_grid():
            sc = score_config([(r["f"], r["future"]) for r in test_m],
                              [r["start_close"] for r in test_m], h["direction"], thr, hor)
            if sc["n"] == 0:
                continue
            wr = sc["wins"] / sc["n"]
            if best is None or wr > best["wr"]:
                lo, hi = wilson_ci(sc["wins"], sc["n"])
                best = {"thr": thr, "hor": hor, "wins": sc["wins"], "n": sc["n"],
                        "wr": wr, "lo": lo, "hi": hi, "avg_move": sc["avg_move_pct"]}
        if best:
            best["p"] = binomial_p(best["wins"], best["n"])
            h["best"] = best
            candidates.append(h)

    # Benjamini-Hochberg across all candidate best-configs
    sig_flags = benjamini_hochberg([h["best"]["p"] for h in candidates], config.FDR_Q)

    events = sum(1 for r in rows if _quick_move(r["start_close"], r["future"]))
    for h, is_sig in zip(candidates, sig_flags):
        b = h["best"]
        # holdout confirmation at the chosen config
        hold_m = h["sel"]["holdout"]
        hwins = sum(1 for r in hold_m
                    if _move_dir_thr(r["start_close"], r["future"], b["thr"], b["hor"]) == h["direction"])
        hlo, _ = wilson_ci(hwins, len(hold_m)) if hold_m else (0.0, 0.0)
        n_occ = b["n"] + len(hold_m)
        stable = (is_sig and hlo >= config.GATE_HOLDOUT_LO and b["lo"] >= config.GATE_TEST_LO
                  and n_occ >= config.GATE_MIN_OCC)
        store.upsert_pattern_stat({
            "pattern_name": h["name"], "source": h["source"],
            "n_train": len(h["sel"]["train"]), "n_test": b["n"],
            "win_rate_train": 0.0, "win_lo_test": b["lo"], "win_hi_test": b["hi"],
            "avg_move_pct": b["avg_move"], "avg_move_hrs": b["hor"],
            "direction": h["direction"], "stable": 1 if stable else 0,
            "threshold": b["thr"], "horizon": b["hor"], "p_value": b["p"],
            "bh_significant": 1 if is_sig else 0, "holdout_lo": hlo,
            "n_holdout": len(hold_m)})

    return {"events_detected": events, "patterns": len(store.all_pattern_stats()),
            "candidates": len(candidates)}


# --- small helpers ---
def _quick_move(start, future):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, config.MOVE_THRESHOLD_PCT,
                           horizon=config.MOVE_WINDOW_HRS)["hit"]


def _move_dir(start, future):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, config.MOVE_THRESHOLD_PCT,
                           horizon=config.MOVE_WINDOW_HRS)["direction"]


def _move_dir_thr(start, future, thr, hor):
    from glory_hype.patterns.stats import forward_outcome
    return forward_outcome(start, future, thr, horizon=hor)["direction"]
