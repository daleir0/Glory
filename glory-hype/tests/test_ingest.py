from glory_hype.db import Store
from glory_hype.narrative.item import NarrativeItem
from glory_hype.narrative.ingest import Ingestor


class GoodAdapter:
    source = "news"
    def fetch(self):
        return [NarrativeItem(ts=1, source="news", reliability_weight=0.7,
                              title="t", body="b", url="u")]


class BoomAdapter:
    source = "social"
    def fetch(self):
        raise RuntimeError("should be caught by ingestor too")


def test_ingest_once_stores_items(tmp_path):
    s = Store(str(tmp_path / "i.db"))
    n = Ingestor(s, adapters=[GoodAdapter()]).ingest_once()
    assert n == 1
    assert len(s.recent_narrative_items(since_ts=0)) == 1


def test_ingest_survives_failing_adapter(tmp_path):
    s = Store(str(tmp_path / "i2.db"))
    n = Ingestor(s, adapters=[BoomAdapter(), GoodAdapter()]).ingest_once()
    assert n == 1  # good adapter still stored despite boom
    assert len(s.recent_narrative_items(since_ts=0)) == 1


def test_ingest_dedupes_across_runs(tmp_path):
    s = Store(str(tmp_path / "i3.db"))
    ing = Ingestor(s, adapters=[GoodAdapter()])
    ing.ingest_once()
    ing.ingest_once()  # same item -> insert-or-ignore
    assert len(s.recent_narrative_items(since_ts=0)) == 1
