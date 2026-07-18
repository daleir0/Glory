"""TradeCall dataclass + defensive parsing of the agent's directional judgment."""

from dataclasses import asdict, dataclass, field

_DIRECTIONS = {"long", "short"}


@dataclass
class TradeCall:
    decision: str                         # long | short | no_trade
    entry: float | None = None
    tp: float | None = None
    sl: float | None = None
    position_notional: float | None = None
    position_coins: float | None = None
    margin: float | None = None
    leverage: float | None = None
    rr: float | None = None
    liq_price: float | None = None
    confidence: float = 0.0
    rationale: str = ""
    gates_failed: list = field(default_factory=list)
    inputs: dict = field(default_factory=dict)
    generated_at: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def no_trade(gates_failed, generated_at, rationale="") -> TradeCall:
    return TradeCall(decision="no_trade", confidence=0.0,
                     gates_failed=list(gates_failed), generated_at=generated_at,
                     rationale=rationale or "No trade: " + "; ".join(gates_failed))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_judgment(j: dict) -> dict:
    """Normalize the agent's judgment. Returns a dict with at least `decision`,
    `entry`, `tp`, `sl`, `confidence`, `rationale`. Invalid direction or missing
    entry/sl downgrade to no_trade."""
    d = j if isinstance(j, dict) else {}
    decision = str(d.get("decision", "")).lower()
    entry, tp, sl = _num(d.get("entry")), _num(d.get("tp")), _num(d.get("sl"))
    conf = _num(d.get("confidence")) or 0.0
    conf = max(0.0, min(1.0, conf))
    rationale = str(d.get("rationale", ""))
    if decision not in _DIRECTIONS:
        return {"decision": "no_trade", "entry": entry, "tp": tp, "sl": sl,
                "confidence": conf,
                "rationale": rationale or "Invalid/!directional judgment."}
    if entry is None or sl is None:
        return {"decision": "no_trade", "entry": entry, "tp": tp, "sl": sl,
                "confidence": conf,
                "rationale": "Incomplete judgment: entry/sl missing."}
    return {"decision": decision, "entry": entry, "tp": tp, "sl": sl,
            "confidence": conf, "rationale": rationale}
