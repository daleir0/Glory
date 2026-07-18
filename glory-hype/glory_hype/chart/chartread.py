"""ChartRead: structured extraction of everything visible on a HYPE chart.

parse_chart_read is defensive — the agent's vision output may be partial or
sloppy, so we coerce/default rather than crash or store a corrupt row."""

from dataclasses import asdict, dataclass, field

_TRENDS = {"up", "down", "range", "unknown"}


def _num(v):
    """Coerce to float or None."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _num_list(v):
    """Keep only numeric entries of a list; non-list -> []."""
    if not isinstance(v, list):
        return []
    out = []
    for x in v:
        n = _num(x)
        if n is not None:
            out.append(n)
    return out


def _str_list(v):
    if not isinstance(v, list):
        return []
    return [str(x) for x in v]


@dataclass
class ChartRead:
    ts: int
    timeframe: str
    exchange_pair: str
    price_range_low: float | None
    price_range_high: float | None
    current_price: float | None
    swing_high: float | None
    swing_low: float | None
    trend: str
    support_levels: list = field(default_factory=list)
    resistance_levels: list = field(default_factory=list)
    patterns: list = field(default_factory=list)
    signals: list = field(default_factory=list)
    indicators: dict = field(default_factory=dict)
    position: dict | None = None
    orders: list = field(default_factory=list)
    annotations: list = field(default_factory=list)
    visible_text: list = field(default_factory=list)
    notes: str = ""
    flags: list = field(default_factory=list)
    image_path: str | None = None
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def parse_chart_read(data: dict, ts: int, image_path: str | None) -> ChartRead:
    d = data if isinstance(data, dict) else {}
    trend = d.get("trend")
    trend = trend if isinstance(trend, str) and trend in _TRENDS else "unknown"
    timeframe = d.get("timeframe")
    timeframe = timeframe if isinstance(timeframe, str) and timeframe else "unknown"
    pair = d.get("exchange_pair")
    pair = pair if isinstance(pair, str) else ""
    position = d.get("position")
    position = position if isinstance(position, dict) else None
    indicators = d.get("indicators")
    indicators = indicators if isinstance(indicators, dict) else {}
    return ChartRead(
        ts=ts,
        timeframe=timeframe,
        exchange_pair=pair,
        price_range_low=_num(d.get("price_range_low")),
        price_range_high=_num(d.get("price_range_high")),
        current_price=_num(d.get("current_price")),
        swing_high=_num(d.get("swing_high")),
        swing_low=_num(d.get("swing_low")),
        trend=trend,
        support_levels=_num_list(d.get("support_levels")),
        resistance_levels=_num_list(d.get("resistance_levels")),
        patterns=_str_list(d.get("patterns")),
        signals=_str_list(d.get("signals")),
        indicators=indicators,
        position=position,
        orders=_str_list(d.get("orders")),
        annotations=_str_list(d.get("annotations")),
        visible_text=_str_list(d.get("visible_text")),
        notes=str(d.get("notes", "")),
        flags=_str_list(d.get("flags")),
        image_path=image_path,
        raw=d,
    )
