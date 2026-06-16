"""Synchronous Hyperliquid REST (info) client. Called from the collector via
asyncio.to_thread so the event loop never blocks."""

import httpx

from glory_hype.config import INFO_URL
from glory_hype.parsers import parse_asset_ctx, parse_candle


class RestClient:
    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=20.0)

    def _post(self, body: dict):
        r = self.http.post(INFO_URL, json=body)
        r.raise_for_status()
        return r.json()

    def close(self) -> None:
        self.http.close()

    def asset_ctx(self, coin: str) -> dict:
        meta, ctxs = self._post({"type": "metaAndAssetCtxs"})
        idx = next((i for i, u in enumerate(meta["universe"]) if u["name"] == coin), None)
        if idx is None:
            raise ValueError(f"{coin} not in Hyperliquid universe")
        return parse_asset_ctx(ctxs[idx])

    def candle_snapshot(self, coin: str, interval: str,
                        start_ms: int, end_ms: int) -> list:
        raw = self._post({"type": "candleSnapshot", "req": {
            "coin": coin, "interval": interval,
            "startTime": start_ms, "endTime": end_ms}})
        return [parse_candle(c) for c in raw]
