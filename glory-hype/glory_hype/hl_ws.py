"""Hyperliquid WebSocket helpers: build subscription messages and route
incoming frames into typed writes. Pure (no socket) for testability."""

from glory_hype.parsers import parse_asset_ctx, parse_candle, parse_trade


def subscribe_messages(coin: str) -> list:
    return [
        {"method": "subscribe", "subscription": {"type": "candle", "coin": coin,
                                                 "interval": "1m"}},
        {"method": "subscribe", "subscription": {"type": "trades", "coin": coin}},
        {"method": "subscribe", "subscription": {"type": "l2Book", "coin": coin}},
        {"method": "subscribe", "subscription": {"type": "activeAssetCtx", "coin": coin}},
    ]


def route_message(msg: dict):
    """Return (kind, payload). kind in {candle, trade, book, ctx, ignore}.
    For candle/trade, payload is a list of typed dicts; for book/ctx a dict."""
    channel = msg.get("channel")
    data = msg.get("data")
    if channel == "candle":
        return "candle", [parse_candle(data)]
    if channel == "trades":
        return "trade", [parse_trade(t) for t in data]
    if channel == "l2Book":
        return "book", {"ts": data["time"], "bids": data["levels"][0],
                        "asks": data["levels"][1]}
    if channel == "activeAssetCtx":
        return "ctx", parse_asset_ctx(data["ctx"])
    return "ignore", None
