"""FastAPI server: multi-asset routes + dashboard page."""

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from glory_hype.db import Store
from glory_hype.events.upcoming import upcoming_events
from glory_hype.narrative.synthesize import Synthesizer
from glory_hype.calc import compute_trade
from glory_hype.chart.record import _write_image, _DEFAULT_CHARTS_DIR
from glory_hype.patterns.detector import current_signal
from glory_hype.track.resolver import track_summary

_STATIC = Path(__file__).parent / "static"


def _snapshot(store: Store) -> dict:
    return {
        "ctx": store.latest_ctx(),
        "large_trades": store.recent_large_trades(20),
        "candles_1m": store.recent_candles("1m", 200),
        "latest_book": store.latest_book(),
    }


def _resolve(assets, slug: str) -> Store:
    store = assets.get(slug)
    if store is None:
        raise HTTPException(status_code=404, detail=f"unknown asset: {slug}")
    return store


def create_app(assets, charts_dir: str = _DEFAULT_CHARTS_DIR) -> FastAPI:
    # Backward compat: bare Store → treat as single-asset "hype"
    if isinstance(assets, Store):
        assets = {"hype": assets}

    app = FastAPI(title="Glory Perp Dashboard")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (_STATIC / "index.html").read_text(encoding="utf-8")

    @app.get("/api/assets")
    def list_assets():
        out = []
        for slug, store in assets.items():
            ctx = store.latest_ctx()
            mark = ctx.get("mark_px") if ctx else None
            prev = ctx.get("prev_day_px") if ctx else None
            change_24h = None
            if mark is not None and prev:
                change_24h = round((mark - prev) / prev * 100, 2)
            out.append({"slug": slug, "coin": slug.upper(),
                        "price": mark, "change_24h": change_24h})
        return out

    @app.get("/api/{asset}/snapshot")
    def snapshot(asset: str):
        return _snapshot(_resolve(assets, asset))

    @app.get("/api/{asset}/health")
    def health(asset: str):
        store = _resolve(assets, asset)
        ctx = store.latest_ctx()
        return {"ctx_ts": ctx["ts"] if ctx else None,
                "candles_1m": len(store.candle_open_timestamps("1m"))}

    @app.get("/api/{asset}/stream")
    async def stream(asset: str):
        store = _resolve(assets, asset)
        async def gen():
            while True:
                snap = await asyncio.to_thread(_snapshot, store)
                yield f"data: {json.dumps(snap)}\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.get("/api/{asset}/narrative")
    def narrative(asset: str):
        store = _resolve(assets, asset)
        since = int(time.time() * 1000) - 24 * 60 * 60 * 1000
        return {"items": store.recent_narrative_items(since_ts=since),
                "conclusion": store.latest_conclusion()}

    @app.post("/api/{asset}/narrative/synthesize")
    async def narrative_synthesize(asset: str):
        store = _resolve(assets, asset)
        def _run():
            syn = Synthesizer(store)
            try:
                return syn.synthesize()
            finally:
                syn.close()
        c = await asyncio.to_thread(_run)
        return c.to_dict()

    @app.get("/api/{asset}/chart")
    def chart(asset: str):
        return {"read": _resolve(assets, asset).latest_chart_read()}

    @app.post("/api/calc")
    async def calc(params: dict):
        try:
            return compute_trade(params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/api/{asset}/chart/upload")
    async def chart_upload(asset: str, file: UploadFile = File(...)):
        store = _resolve(assets, asset)
        if not (file.content_type or "").startswith("image/"):
            raise HTTPException(status_code=400, detail="file must be an image")
        data = await file.read()
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="image exceeds 10 MB")
        ts = int(time.time() * 1000)
        path = Path(charts_dir) / f"{asset}-{ts}.png"
        try:
            _write_image(path, data)
        except Exception:
            raise HTTPException(status_code=500, detail="failed to save image")
        store.insert_pending_chart_read(ts=ts, image_path=str(path))
        return {"ts": ts, "image_path": str(path), "status": "pending"}

    @app.get("/api/{asset}/chart/pending")
    def chart_pending(asset: str):
        return {"pending": _resolve(assets, asset).pending_chart_reads()}

    @app.get("/api/{asset}/decision")
    def decision(asset: str):
        return {"call": _resolve(assets, asset).latest_trade_call()}

    @app.get("/api/{asset}/settings")
    def get_settings(asset: str):
        return {"settings": _resolve(assets, asset).get_settings()}

    @app.post("/api/{asset}/settings")
    def post_settings(asset: str, body: dict):
        store = _resolve(assets, asset)
        for k, v in body.items():
            store.set_setting(k, v)
        return {"settings": store.get_settings()}

    @app.get("/api/{asset}/track")
    def track(asset: str):
        store = _resolve(assets, asset)
        calls = store.recent_trade_calls(since_ts=0)
        closed = [c for c in calls if c.get("status") in ("win", "loss")]
        return {"stats": track_summary(store), "recent": closed[:20]}

    @app.get("/api/{asset}/patterns")
    def patterns(asset: str):
        store = _resolve(assets, asset)
        sig = current_signal(store)
        return {"regime": sig["regime"], "matches": sig["matches"],
                "library": store.all_pattern_stats()}

    @app.get("/api/{asset}/events")
    def events(asset: str):
        store = _resolve(assets, asset)
        now = int(time.time() * 1000)
        return {"upcoming": upcoming_events(store, now, 30),
                "playbook": store.all_event_studies()}

    @app.post("/api/{asset}/events/analyze")
    async def events_analyze(asset: str):
        from glory_hype.events.upcoming import analyze_events
        store = _resolve(assets, asset)
        result = await asyncio.to_thread(lambda: analyze_events(store))
        return result

    return app
