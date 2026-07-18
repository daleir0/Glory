"""Conclusion: the reliability-weighted narrative verdict + JSON parsing."""

import json
import re
from dataclasses import asdict, dataclass, field

_SIGN = {"bullish": 1, "bearish": -1, "neutral": 0}


@dataclass
class Conclusion:
    bias: str
    confidence: float
    score: int
    key_drivers: list = field(default_factory=list)
    caution_flags: list = field(default_factory=list)
    source_breakdown: dict = field(default_factory=dict)
    based_on: list = field(default_factory=list)
    generated_at: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _score(bias: str, confidence: float) -> int:
    return _SIGN.get(bias, 0) * round(confidence * 100)


def unavailable(generated_at: int) -> Conclusion:
    return Conclusion(bias="neutral", confidence=0.0, score=0,
                      caution_flags=["synthesis unavailable"],
                      generated_at=generated_at)


def _extract_json(raw: str):
    # Try fenced block first, then a brace-balanced scan from the first '{'.
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    start = raw.find("{")
    if start == -1:
        raise ValueError("no json found")
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(raw[start:i + 1])
    raise ValueError("unbalanced json")


def _strip_thinking(raw: str) -> str:
    return re.sub(r"<thinking>.*?</thinking>", "", raw, flags=re.DOTALL).strip()


def parse_conclusion(raw: str, based_on: list, generated_at: int) -> Conclusion:
    try:
        d = _extract_json(_strip_thinking(raw))
        bias = str(d.get("bias", "neutral")).lower()
        if bias not in _SIGN:
            bias = "neutral"
        confidence = max(0.0, min(1.0, float(d.get("confidence", 0.0))))
        return Conclusion(
            bias=bias, confidence=confidence, score=_score(bias, confidence),
            key_drivers=list(d.get("key_drivers", [])),
            caution_flags=list(d.get("caution_flags", [])),
            source_breakdown=dict(d.get("source_breakdown", {})),
            based_on=based_on, generated_at=generated_at)
    except Exception:
        c = unavailable(generated_at)
        c.based_on = based_on
        return c
