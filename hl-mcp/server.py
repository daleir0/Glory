import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BASE_URL = "https://api.hyperliquid.xyz"
mcp = FastMCP("hl-trader")


def _exchange():
    pk = os.environ["HL_PRIVATE_KEY"]
    wallet = Account.from_key(pk)
    return Exchange(wallet, BASE_URL), wallet.address


def _info():
    return Info(BASE_URL, skip_ws=True)


@mcp.tool()
def hl_get_account() -> dict:
    """Get account state: margin summary, balances, account value."""
    exchange, addr = _exchange()
    return _info().user_state(addr)


@mcp.tool()
def hl_get_positions() -> list:
    """Get all open perpetual positions."""
    exchange, addr = _exchange()
    state = _info().user_state(addr)
    return state.get("assetPositions", [])


@mcp.tool()
def hl_get_open_orders() -> list:
    """Get all open orders."""
    exchange, addr = _exchange()
    return _info().open_orders(addr)


@mcp.tool()
def hl_place_order(
    coin: str,
    is_buy: bool,
    sz: float,
    limit_px: float,
    tif: str = "Gtc",
    reduce_only: bool = False,
) -> dict:
    """
    Place a limit order on Hyperliquid perps.
    coin: asset symbol, e.g. 'HYPE', 'BTC', 'ETH'
    is_buy: True = long/buy, False = short/sell
    sz: size in base asset units
    limit_px: limit price in USD
    tif: 'Gtc' (good-till-cancel), 'Ioc' (immediate-or-cancel), 'Alo' (post-only)
    reduce_only: only reduce an existing position
    """
    exchange, _ = _exchange()
    order_type = {"limit": {"tif": tif}}
    return exchange.order(coin, is_buy, sz, limit_px, order_type, reduce_only=reduce_only)


@mcp.tool()
def hl_market_order(coin: str, is_buy: bool, sz: float, slippage_pct: float = 1.0) -> dict:
    """
    Place a market order (aggressive IOC limit with slippage buffer).
    coin: asset symbol
    is_buy: True = long/buy, False = short/sell
    sz: size in base asset units
    slippage_pct: max slippage tolerance in percent (default 1%)
    """
    exchange, _ = _exchange()
    mids = _info().all_mids()
    mid = float(mids[coin])
    if is_buy:
        limit_px = round(mid * (1 + slippage_pct / 100), 6)
    else:
        limit_px = round(mid * (1 - slippage_pct / 100), 6)
    order_type = {"limit": {"tif": "Ioc"}}
    return exchange.order(coin, is_buy, sz, limit_px, order_type)


@mcp.tool()
def hl_cancel_order(coin: str, oid: int) -> dict:
    """Cancel a specific order by coin and order ID."""
    exchange, _ = _exchange()
    return exchange.cancel(coin, oid)


@mcp.tool()
def hl_cancel_all(coin: str = "") -> dict:
    """Cancel all open orders. Pass coin to limit to one asset."""
    exchange, addr = _exchange()
    orders = _info().open_orders(addr)
    if coin:
        orders = [o for o in orders if o["coin"] == coin]
    results = [exchange.cancel(o["coin"], o["oid"]) for o in orders]
    return {"cancelled": len(results), "results": results}


@mcp.tool()
def hl_close_position(coin: str, slippage_pct: float = 1.0) -> dict:
    """Close the entire open position for a coin at market price."""
    exchange, addr = _exchange()
    info = _info()
    state = info.user_state(addr)
    positions = state.get("assetPositions", [])
    pos = next((p for p in positions if p["position"]["coin"] == coin), None)
    if not pos:
        return {"error": f"No open position for {coin}"}
    szi = float(pos["position"]["szi"])
    is_buy = szi < 0  # closing a short = buy
    sz = abs(szi)
    mid = float(info.all_mids()[coin])
    limit_px = round(mid * (1 + slippage_pct / 100) if is_buy else mid * (1 - slippage_pct / 100), 6)
    order_type = {"limit": {"tif": "Ioc"}}
    return exchange.order(coin, is_buy, sz, limit_px, order_type, reduce_only=True)


@mcp.tool()
def hl_set_leverage(coin: str, leverage: int, is_cross: bool = True) -> dict:
    """Set leverage for a coin. is_cross=True for cross margin, False for isolated."""
    exchange, _ = _exchange()
    return exchange.update_leverage(leverage, coin, is_cross)


@mcp.tool()
def hl_get_mid_prices(coins: list[str] = None) -> dict:
    """Get current mid prices. Pass coins list to filter, or empty for all."""
    mids = _info().all_mids()
    if coins:
        return {c: mids[c] for c in coins if c in mids}
    return mids


if __name__ == "__main__":
    mcp.run()
