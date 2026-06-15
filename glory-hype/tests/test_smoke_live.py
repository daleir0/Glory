import asyncio
import time

import pytest

from glory_hype.collector import Collector
from glory_hype.db import Store

pytestmark = pytest.mark.live


def test_live_backfill_and_poll(tmp_path):
    """Real network: backfill 1m candles + one ctx poll, then assert rows landed."""
    store = Store(str(tmp_path / "live.db"))
    col = Collector(store)
    col.backfill_interval("1m")
    col.poll_once(now_ms=int(time.time() * 1000))
    assert store.latest_candle("1m") is not None
    ctx = store.latest_ctx()
    assert ctx is not None and ctx["mark_px"] > 0


def test_live_ws_receives_messages(tmp_path):
    """Real network: connect WS, ingest ~5s, assert at least one candle row."""
    store = Store(str(tmp_path / "ws.db"))
    col = Collector(store)

    async def run_for(seconds):
        task = asyncio.create_task(col._ws_loop())
        await asyncio.sleep(seconds)
        task.cancel()

    asyncio.run(run_for(8))
    assert store.latest_candle("1m") is not None
