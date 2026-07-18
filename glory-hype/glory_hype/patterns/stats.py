"""Wilson confidence interval + leak-free forward outcome labeling."""

import math


def wilson_ci(wins: int, n: int, z: float = 1.96):
    """95% Wilson score interval for a binomial proportion. Returns (lo, hi)."""
    if n == 0:
        return (0.0, 0.0)
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - margin) / denom, (centre + margin) / denom)


def binomial_p(wins: int, n: int, p0: float = 0.5) -> float:
    """One-sided p-value: P(X >= wins) for X ~ Binomial(n, p0). 1.0 if n == 0."""
    if n == 0:
        return 1.0
    # survival function via summation (n is small here)
    from math import comb
    tail = sum(comb(n, k) * (p0 ** k) * ((1 - p0) ** (n - k))
               for k in range(wins, n + 1))
    return min(1.0, tail)


def benjamini_hochberg(pvalues: list, q: float = 0.05) -> list:
    """Return a list of bools: which hypotheses are significant under BH-FDR at q.
    Preserves input order."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    sig = [False] * m
    max_k = -1
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= q * rank / m:
            max_k = rank
    if max_k >= 0:
        for rank, idx in enumerate(order, start=1):
            if rank <= max_k:
                sig[idx] = True
    return sig


def forward_outcome(start_close: float, future: list, threshold_pct: float,
                    horizon: int | None = None) -> dict:
    """Largest signed move from start_close over the future candles. 'hit' if the
    peak magnitude reached threshold. Leak-free: caller passes only candles strictly
    after the feature window. If horizon is given, only the first `horizon`
    candles are considered."""
    if horizon is not None:
        future = future[:horizon]
    if not future or not start_close:
        return {"direction": "none", "move_pct": 0.0, "hit": False}
    max_up = max((c["h"] - start_close) / start_close * 100 for c in future)
    max_dn = min((c["l"] - start_close) / start_close * 100 for c in future)
    # the dominant move is whichever magnitude is larger
    if abs(max_dn) > max_up:
        move = max_dn
        direction = "down" if abs(move) >= threshold_pct else "none"
    else:
        move = max_up
        direction = "up" if move >= threshold_pct else "none"
    return {"direction": direction, "move_pct": move,
            "hit": abs(move) >= threshold_pct}
