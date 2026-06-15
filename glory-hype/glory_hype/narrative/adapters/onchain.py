"""Derive narrative events from our own guaranteed hype.db data."""

from glory_hype.narrative.item import NarrativeItem
from glory_hype.narrative.store_api import now_ms

_WEIGHT = 1.0


class OnchainAdapter:
    source = "onchain"

    def __init__(self, store, oi_surge_pct: float = 8.0,
                 large_cluster_min: int = 5, window_ms: int = 600_000):
        self.store = store
        self.oi_surge_pct = oi_surge_pct
        self.large_cluster_min = large_cluster_min
        self.window_ms = window_ms

    def fetch(self) -> list[NarrativeItem]:
        try:
            return self._fetch()
        except Exception:
            return []

    def _fetch(self) -> list[NarrativeItem]:
        items = []
        ts = now_ms()
        hist = self.store.ctx_history(limit=2)
        if len(hist) >= 2:
            latest, prev = hist[0], hist[1]
            # OI surge
            if prev["open_interest"]:
                chg = (latest["open_interest"] - prev["open_interest"]) / prev["open_interest"] * 100
                if abs(chg) >= self.oi_surge_pct:
                    direction = "surged" if chg > 0 else "dropped"
                    items.append(NarrativeItem(
                        ts=ts, source=self.source, reliability_weight=_WEIGHT,
                        title=f"Open interest {direction} {chg:+.1f}%",
                        body=f"OI moved from {prev['open_interest']:.0f} to "
                             f"{latest['open_interest']:.0f} HYPE.",
                        url=None))
            # Funding flip
            if (latest["funding"] > 0) != (prev["funding"] > 0):
                items.append(NarrativeItem(
                    ts=ts, source=self.source, reliability_weight=_WEIGHT,
                    title="Funding rate flipped sign",
                    body=f"Funding went from {prev['funding']:.6f} to "
                         f"{latest['funding']:.6f}.",
                    url=None))
        # Large-trade cluster
        n = self.store.count_large_trades_since(now_ms() - self.window_ms)
        if n >= self.large_cluster_min:
            items.append(NarrativeItem(
                ts=ts, source=self.source, reliability_weight=_WEIGHT,
                title=f"Large-trade cluster: {n} prints",
                body=f"{n} large trades in the last {self.window_ms // 60000} min.",
                url=None))
        return items
