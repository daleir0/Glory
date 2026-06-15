"""Pure candle-gap detection over a sorted list of open timestamps."""


def find_candle_gaps(open_ts: list, interval_ms: int) -> list:
    """Return the open timestamps that SHOULD exist between the first and last
    given timestamps but are missing. Assumes input is sorted ascending."""
    if len(open_ts) < 2:
        return []
    present = set(open_ts)
    missing = []
    t = open_ts[0] + interval_ms
    last = open_ts[-1]
    while t < last:
        if t not in present:
            missing.append(t)
        t += interval_ms
    return missing
