"""Narrative ingest: poll adapters, dedupe, store. Resilient to adapter failure."""

import asyncio
import logging

from glory_hype.narrative.item import dedupe_items

log = logging.getLogger(__name__)

INGEST_INTERVAL_SEC = 120


class Ingestor:
    def __init__(self, store, adapters):
        self.store = store
        self.adapters = adapters

    def ingest_once(self) -> int:
        collected = []
        for adapter in self.adapters:
            try:
                collected.extend(adapter.fetch())
            except Exception as e:
                log.warning("adapter %s failed: %s", getattr(adapter, "source", "?"), e)
        stored = 0
        for item in dedupe_items(collected):
            if self.store.insert_narrative_item(item):
                stored += 1
        return stored

    async def run(self):
        while True:
            try:
                n = await asyncio.to_thread(self.ingest_once)
                log.info("ingested %d new narrative items", n)
            except Exception as e:
                log.exception("ingest cycle error: %s", e)
            await asyncio.sleep(INGEST_INTERVAL_SEC)
