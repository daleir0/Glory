"""Social/X sentiment slot. No-op until a viable feed is wired in v2.x."""

from glory_hype.narrative.item import NarrativeItem


class SocialAdapter:
    source = "social"

    def fetch(self) -> list[NarrativeItem]:
        return []
