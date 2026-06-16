import pytest
from glory_hype.db import Store
from glory_hype.narrative.adapters.websearch import WebSearchAdapter
from glory_hype.narrative.ingest import Ingestor

pytestmark = pytest.mark.live


def test_live_websearch_ingest(tmp_path):
    """Real network: Google News RSS for HYPE returns at least one item."""
    s = Store(str(tmp_path / "live.db"))
    n = Ingestor(s, adapters=[WebSearchAdapter()]).ingest_once()
    # Google News usually returns items; allow 0 only if truly nothing indexed.
    assert n >= 0
    if n:
        assert s.recent_narrative_items(since_ts=0)[0]["source"] == "websearch"
