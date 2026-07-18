"""Pure outcome resolution: did a call hit TP or SL first, per our candles?"""

_NA = {"status": "n/a", "exit_price": None, "exit_ts": None,
       "r_multiple": None, "ambiguous": False}


def resolve_outcome(call: dict, candles: list) -> dict:
    decision = call.get("decision")
    entry, tp, sl = call.get("entry"), call.get("tp"), call.get("sl")
    if decision not in ("long", "short") or entry is None or tp is None or sl is None:
        return dict(_NA)

    risk = abs(entry - sl)
    reward = abs(tp - entry)
    win_r = round(reward / risk, 4) if risk else None

    def win(c):
        return {"status": "win", "exit_price": float(tp), "exit_ts": c["open_ts"],
                "r_multiple": win_r, "ambiguous": False}

    def loss(c, ambiguous=False):
        return {"status": "loss", "exit_price": float(sl), "exit_ts": c["open_ts"],
                "r_multiple": -1.0, "ambiguous": ambiguous}

    # Phase 1: the entry must actually fill before TP/SL can be scored. The entry
    # is touched when a candle's range spans it (low <= entry <= high). Without
    # this, a limit that never filled was wrongly scored a win when price later
    # passed through TP (the v5 phantom-win bug).
    filled_idx = None
    for i, c in enumerate(candles):
        if c["l"] <= entry <= c["h"]:
            filled_idx = i
            break
    if filled_idx is None:
        return {"status": "unfilled", "exit_price": None, "exit_ts": None,
                "r_multiple": None, "ambiguous": False}

    # Phase 2: from the fill candle onward, did TP or SL hit first?
    for c in candles[filled_idx:]:
        hi, lo = c["h"], c["l"]
        if decision == "long":
            hit_sl, hit_tp = lo <= sl, hi >= tp
        else:  # short
            hit_sl, hit_tp = hi >= sl, lo <= tp
        if hit_sl and hit_tp:
            return loss(c, ambiguous=True)   # conservative: assume stop first
        if hit_sl:
            return loss(c)
        if hit_tp:
            return win(c)
    return {"status": "open", "exit_price": None, "exit_ts": None,
            "r_multiple": None, "ambiguous": False}
