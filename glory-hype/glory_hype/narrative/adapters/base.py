"""SourceAdapter interface. Each adapter fetches normalized NarrativeItems."""

from typing import Protocol

from glory_hype.narrative.item import NarrativeItem


class SourceAdapter(Protocol):
    source: str

    def fetch(self) -> list[NarrativeItem]:
        """Return current narrative items from this source. Must not raise on
        network/source failure — return [] and let the caller log."""
        ...
