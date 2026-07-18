"""Threshold/horizon sweep: enumerate configs and score a pattern at each."""

from glory_hype import config
from glory_hype.patterns.stats import forward_outcome


def config_grid():
    return [(t, h) for t in config.SWEEP_THRESHOLDS for h in config.SWEEP_HORIZONS]


def score_config(members: list, start_closes: list, direction: str,
                 threshold: float, horizon: int) -> dict:
    """members: list of (features, future_candles). start_closes aligned to members.
    Returns wins (forward move matched `direction` at this threshold/horizon) and n."""
    wins, n, moves = 0, 0, []
    for (_, future), sc in zip(members, start_closes):
        o = forward_outcome(sc, future, threshold, horizon=horizon)
        n += 1
        if o["direction"] == direction:
            wins += 1
        if o["hit"]:
            moves.append(abs(o["move_pct"]))
    return {"wins": wins, "n": n, "threshold": threshold, "horizon": horizon,
            "avg_move_pct": (sum(moves) / len(moves)) if moves else 0.0}
