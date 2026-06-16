"""Resolve open trade calls against stored candles; summarize the track record."""

from glory_hype.track.outcomes import resolve_outcome
from glory_hype.track.stats import compute_stats


def resolve_open_calls(store) -> dict:
    for call in store.open_trade_calls():
        candles = store.candles_since("1m", call["generated_at"])
        outcome = resolve_outcome(call, candles)
        if outcome["status"] in ("win", "loss"):
            store.update_call_outcome(call["generated_at"], outcome)
    return track_summary(store)


def track_summary(store) -> dict:
    return compute_stats(store.recent_trade_calls(since_ts=0))
