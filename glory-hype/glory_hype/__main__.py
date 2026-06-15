"""CLI: python -m glory_hype <collect|serve|verify|ingest|narrative> [--asset SLUG] [--port N]"""

import argparse
import asyncio
import json as _json

import uvicorn

from glory_hype import config
from glory_hype.collector import Collector
from glory_hype.db import Store
from glory_hype.hl_rest import RestClient
from glory_hype.narrative.adapters.news import NewsAdapter
from glory_hype.narrative.adapters.onchain import OnchainAdapter
from glory_hype.narrative.adapters.social import SocialAdapter
from glory_hype.narrative.adapters.websearch import WebSearchAdapter
from glory_hype.narrative.ingest import Ingestor
from glory_hype.narrative.synthesize import Synthesizer
from glory_hype.chart.record import record_chart_read, finalize_chart_read
from glory_hype.decision.engine import record_call
from glory_hype.events.catalog import seed_catalog
from glory_hype.events.upcoming import analyze_events, upcoming_events
from glory_hype.patterns.backtest import run_backtest
from glory_hype.patterns.detector import current_signal
from glory_hype.server import create_app
from glory_hype.verify import verify_ctx
from glory_hype.track.resolver import resolve_open_calls


def _asset_stores(asset_slug: str | None) -> dict:
    """Return {slug: Store} for the given slug, or all known assets if None."""
    from pathlib import Path
    if asset_slug:
        slugs = [asset_slug.lower()]
    else:
        # Auto-discover: any registered asset whose DB file exists on disk
        slugs = [s for s, cfg in config.ASSETS.items()
                 if Path(cfg.db).exists() or s == "hype"]
        if not slugs:
            slugs = ["hype"]
    stores = {}
    for slug in slugs:
        cfg = config.ASSETS.get(slug)
        db_path = cfg.db if cfg else config.DB_PATH
        stores[slug] = Store(db_path)
    return stores


def main():
    p = argparse.ArgumentParser(prog="glory_hype")
    p.add_argument("cmd", choices=["collect", "serve", "verify", "ingest", "narrative", "chart", "decide", "track", "patterns", "events"])
    p.add_argument("--asset", default=None, help="asset slug (e.g. hype, near); defaults to hype")
    p.add_argument("--db", default=None, help="override DB path (deprecated; use --asset)")
    p.add_argument("--port", type=int, default=5179)
    p.add_argument("--file", help="path to ChartRead JSON (for `chart`)")
    p.add_argument("--image", help="path to chart screenshot (for `chart`)")
    p.add_argument("--pending", action="store_true",
                   help="list pending chart reads (for `chart`)")
    p.add_argument("--finalize", type=int, metavar="TS",
                   help="finalize the pending chart read at this ts (for `chart`)")
    p.add_argument("--mode", default="now", choices=["analyze", "now"],
                   help="patterns mode: analyze (run backtest) or now (live signal)")
    p.add_argument("--events-mode", default="upcoming",
                   choices=["seed", "analyze", "upcoming"])
    args = p.parse_args()

    # Resolve store(s): --db takes precedence for single-asset commands
    slug = (args.asset or "hype").lower()
    if args.db:
        store = Store(args.db)
        all_stores = {slug: store}
    else:
        all_stores = _asset_stores(args.asset)
        store = all_stores.get(slug) or next(iter(all_stores.values()))

    if args.cmd == "collect":
        asyncio.run(Collector(store).run())
    elif args.cmd == "serve":
        uvicorn.run(create_app(all_stores), host="0.0.0.0", port=args.port)
    elif args.cmd == "verify":
        client = RestClient()
        try:
            ok, report = verify_ctx(store, client)
        finally:
            client.close()
        print(report)
        raise SystemExit(0 if ok else 1)
    elif args.cmd == "ingest":
        adapters = [OnchainAdapter(store), NewsAdapter(), WebSearchAdapter(), SocialAdapter()]
        asyncio.run(Ingestor(store, adapters).run())
    elif args.cmd == "narrative":
        syn = Synthesizer(store)
        try:
            c = syn.synthesize()
        finally:
            syn.close()
        print(_json.dumps(c.to_dict(), indent=2))
    elif args.cmd == "decide":
        with open(args.file, encoding="utf-8") as f:
            judgment = _json.load(f)
        call = record_call(store, judgment)
        print(_json.dumps(call.to_dict(), indent=2))
    elif args.cmd == "track":
        stats = resolve_open_calls(store)
        print(_json.dumps(stats, indent=2))
    elif args.cmd == "patterns":
        if args.mode == "analyze":
            print(_json.dumps(run_backtest(store), indent=2))
        else:
            print(_json.dumps(current_signal(store), indent=2, default=str))
    elif args.cmd == "events":
        import time as _t
        if args.events_mode == "seed":
            print(_json.dumps({"added": seed_catalog(store)}, indent=2))
        elif args.events_mode == "analyze":
            print(_json.dumps(analyze_events(store), indent=2, default=str))
        else:
            print(_json.dumps(upcoming_events(store, int(_t.time() * 1000), 30),
                              indent=2, default=str))
    elif args.cmd == "chart":
        if args.pending:
            print(_json.dumps(store.pending_chart_reads(), indent=2))
        elif args.finalize is not None:
            with open(args.file, encoding="utf-8") as f:
                data = _json.load(f)
            read = finalize_chart_read(store, args.finalize, data)
            print(_json.dumps(read.to_dict(), indent=2))
        else:
            with open(args.file, encoding="utf-8") as f:
                data = _json.load(f)
            image_bytes = None
            if args.image:
                with open(args.image, "rb") as f:
                    image_bytes = f.read()
            read = record_chart_read(store, data, image_bytes=image_bytes)
            print(_json.dumps(read.to_dict(), indent=2))


if __name__ == "__main__":
    main()
