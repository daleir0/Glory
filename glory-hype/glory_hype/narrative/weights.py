"""Source reliability weights. Higher = more trusted in synthesis."""

RELIABILITY = {
    "onchain": 1.0,    # our own guaranteed data
    "news": 0.7,       # structured crypto outlets
    "websearch": 0.6,  # broad web/news search
    "social": 0.3,     # noisy, best-effort
}


def weight_for(source: str) -> float:
    return RELIABILITY.get(source, 0.3)
