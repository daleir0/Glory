"""Verify stored market context matches the live exchange within tolerance."""

from glory_hype.config import COIN

_FIELDS = ["mark_px", "oracle_px", "mid_px", "open_interest"]


def verify_ctx(store, rest, tol_pct: float = 0.5):
    """Compare latest stored ctx vs live. Returns (ok, human_report)."""
    stored = store.latest_ctx()
    if stored is None:
        return False, "FAIL: no stored market_ctx rows yet."
    live = rest.asset_ctx(COIN)
    lines = []
    ok = True
    for f in _FIELDS:
        s, l = stored[f], live[f]
        denom = abs(l) if l else 1.0
        diff_pct = abs(s - l) / denom * 100
        flag = "OK" if diff_pct <= tol_pct else "MISMATCH"
        if diff_pct > tol_pct:
            ok = False
        lines.append(f"  {f}: stored={s} live={l} diff={diff_pct:.3f}% [{flag}]")
    header = "PASS" if ok else "FAIL"
    return ok, header + "\n" + "\n".join(lines)
