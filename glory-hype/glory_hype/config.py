"""Static configuration for the glory-hype data foundation."""

from dataclasses import dataclass

INFO_URL = "https://api.hyperliquid.xyz/info"
WS_URL = "wss://api.hyperliquid.xyz/ws"

COIN = "HYPE"

INTERVALS = ["1m", "5m", "15m", "1h", "4h", "1d"]
INTERVAL_MS = {
    "1m": 60_000, "5m": 300_000, "15m": 900_000,
    "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000,
}

LARGE_TRADE_NTL_USD = 50_000.0
POLL_INTERVAL_SEC = 30
DB_PATH = "hype.db"
BACKFILL_LIMIT = 5000

# --- v10 multi-perp asset registry ---
@dataclass
class AssetConfig:
    coin: str
    db: str
    large_trade_ntl: float

ASSETS: dict[str, AssetConfig] = {
    "hype": AssetConfig(coin="HYPE", db="hype.db", large_trade_ntl=50_000),
    "near": AssetConfig(coin="NEAR", db="near.db", large_trade_ntl=5_000),
    "icp":  AssetConfig(coin="ICP",  db="icp.db",  large_trade_ntl=5_000),
    "vvv":  AssetConfig(coin="VVV",  db="vvv.db",  large_trade_ntl=5_000),
}

# --- v10 LM Studio (Gemma) synthesis ---
LM_STUDIO_URL = "http://169.254.83.107:1234"
LM_STUDIO_MODEL = "90f9618340396838ee7ff5b0ba2da27da62953d3"

# --- v4 decision engine ---
MIN_RR = 1.5
NARRATIVE_STALE_MS = 12 * 60 * 60 * 1000
CTX_STALE_MS = 5 * 60 * 1000
DEFAULT_RISK_PCT = 0.01
DEFAULT_LEVERAGE = 10

# --- v9 pattern intelligence ---
PATTERN_MIN_OCCURRENCES = 10
PATTERN_SIGNAL_CONF = 0.60
PATTERN_TRAIN_FRAC = 0.70
MOVE_THRESHOLD_PCT = 4.0
MOVE_WINDOW_HRS = 6
PATTERN_CONF_MODIFIER_MAX = 0.15

# --- v9.1 pattern deepening ---
SWEEP_THRESHOLDS = [2.0, 3.0, 5.0, 7.0]
SWEEP_HORIZONS = [2, 6, 12, 24]
FDR_Q = 0.05
SPLIT_TRAIN = 0.60
SPLIT_TEST = 0.20
OOS_MAX_DIST = 2.5
GATE_MIN_OCC = 15
GATE_TEST_LO = 0.60
GATE_HOLDOUT_LO = 0.55
OI_SURGE_PCT = 5.0

# --- v9.2 event-anchored intelligence ---
EVENT_WINDOW_DAYS = 7
EVENT_ALERT_DAYS = 14
EVENT_CAUTION_HRS = 48
EVENT_PROXIMITY_DAYS = 3
