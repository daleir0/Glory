"""NarrativeItem: one normalized narrative signal, with content-hash dedupe."""

import hashlib
from dataclasses import dataclass, field


def content_hash(source: str, title: str, url: str | None) -> str:
    raw = f"{source}\x1f{title}\x1f{url or ''}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class NarrativeItem:
    ts: int                    # epoch ms
    source: str                # onchain | news | websearch | social
    reliability_weight: float
    title: str
    body: str
    url: str | None = None
    hash: str = field(default="", init=True)

    def __post_init__(self):
        if not self.hash:
            self.hash = content_hash(self.source, self.title, self.url)


def dedupe_items(items: list[NarrativeItem]) -> list[NarrativeItem]:
    seen = set()
    out = []
    for it in items:
        if it.hash in seen:
            continue
        seen.add(it.hash)
        out.append(it)
    return out
