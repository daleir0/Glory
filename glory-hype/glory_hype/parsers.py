"""Pure parsers turning raw Hyperliquid JSON into typed dicts. No I/O."""

from glory_hype.config import LARGE_TRADE_NTL_USD


def is_large_trade(px: float, sz: float) -> bool:
    return px * sz >= LARGE_TRADE_NTL_USD


def parse_candle(raw: dict) -> dict:
    """Raw candle (REST candleSnapshot item or WS candle.data) -> typed dict."""
    return {
        "interval": raw["i"],
        "open_ts": int(raw["t"]),
        "close_ts": int(raw["T"]),
        "o": float(raw["o"]),
        "h": float(raw["h"]),
        "l": float(raw["l"]),
        "c": float(raw["c"]),
        "v": float(raw["v"]),
        "n": int(raw["n"]),
    }


def parse_asset_ctx(raw: dict) -> dict:
    """Asset context (REST metaAndAssetCtxs[1][i] or WS activeAssetCtx.data.ctx)."""
    return {
        "funding": float(raw["funding"]),
        "open_interest": float(raw["openInterest"]),
        "mark_px": float(raw["markPx"]),
        "oracle_px": float(raw["oraclePx"]),
        "mid_px": float(raw["midPx"]),
        "premium": float(raw["premium"]),
        "prev_day_px": float(raw["prevDayPx"]),
        "day_ntl_vlm": float(raw["dayNtlVlm"]),
    }


def parse_trade(raw: dict) -> dict:
    """Raw WS trade -> typed dict with notional and large flag."""
    px = float(raw["px"])
    sz = float(raw["sz"])
    return {
        "ts": int(raw["time"]),
        "px": px,
        "sz": sz,
        "side": raw["side"],
        "tid": int(raw["tid"]),
        "ntl": px * sz,
        "is_large": is_large_trade(px, sz),
    }
