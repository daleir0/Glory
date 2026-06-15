"""Collector daemon: backfill history, stream live WS data, poll REST context,
and self-heal candle gaps. Composes the tested parser/db/ws/rest units."""

import asyncio
import json
import time

import websockets

from glory_hype import config
from glory_hype.db import Store
from glory_hype.gaps import find_candle_gaps
from glory_hype.hl_rest import RestClient
from glory_hype.hl_ws import route_message, subscribe_messages


class Collector:
    def __init__(self, store: Store, rest=None):
        self.store = store
        self.rest = rest or RestClient()

    # --- composable units (unit-tested) ---
    def backfill_interval(self, interval: str) -> None:
        now = int(time.time() * 1000)
        span = config.INTERVAL_MS[interval] * config.BACKFILL_LIMIT
        candles = self.rest.candle_snapshot(config.COIN, interval, now - span, now)
        for c in candles:
            self.store.insert_candle(c)

    def poll_once(self, now_ms: int) -> None:
        ctx = self.rest.asset_ctx(config.COIN)
        self.store.insert_ctx(ctx, ts=now_ms)

    def heal_gaps(self, interval: str) -> int:
        ts = self.store.candle_open_timestamps(interval)
        missing = find_candle_gaps(ts, config.INTERVAL_MS[interval])
        if not missing:
            return 0
        candles = self.rest.candle_snapshot(
            config.COIN, interval, missing[0], missing[-1] + config.INTERVAL_MS[interval])
        for c in candles:
            self.store.insert_candle(c)
        return len(missing)

    def apply_ws_message(self, msg: dict) -> None:
        kind, payload = route_message(msg)
        if kind == "candle":
            for c in payload:
                self.store.insert_candle(c)
        elif kind == "trade":
            for t in payload:
                self.store.insert_trade(t)
        elif kind == "book":
            self.store.insert_book(payload["ts"], payload["bids"], payload["asks"])
        elif kind == "ctx":
            self.store.insert_ctx(payload, ts=int(time.time() * 1000))

    # --- async loops (exercised by the live smoke) ---
    async def _poll_loop(self):
        while True:
            try:
                await asyncio.to_thread(self.poll_once, int(time.time() * 1000))
                for iv in config.INTERVALS:
                    await asyncio.to_thread(self.backfill_recent, iv)
                    await asyncio.to_thread(self.heal_gaps, iv)
            except Exception as e:  # keep the daemon alive
                print(f"[poll] error: {e}")
            await asyncio.sleep(config.POLL_INTERVAL_SEC)

    def backfill_recent(self, interval: str) -> None:
        """Refresh the last few candles of an interval to keep them current."""
        now = int(time.time() * 1000)
        span = config.INTERVAL_MS[interval] * 5
        for c in self.rest.candle_snapshot(config.COIN, interval, now - span, now):
            self.store.insert_candle(c)

    async def _ws_loop(self):
        while True:
            try:
                async with websockets.connect(config.WS_URL, open_timeout=15) as ws:
                    for m in subscribe_messages(config.COIN):
                        await ws.send(json.dumps(m))
                    print("[ws] connected + subscribed")
                    async for raw in ws:
                        self.apply_ws_message(json.loads(raw))
            except Exception as e:
                print(f"[ws] disconnected: {e}; reconnecting in 3s")
                await asyncio.sleep(3)

    async def run(self):
        # backfill once, then run poller + ws concurrently forever
        for iv in config.INTERVALS:
            await asyncio.to_thread(self.backfill_interval, iv)
        print("[collector] backfill complete; going live")
        await asyncio.gather(self._poll_loop(), self._ws_loop())
