from glory_hype.db import Store
from glory_hype.events.catalog import SEED_EVENTS, seed_catalog


def test_seed_has_monthly_unlocks_and_future():
    types = [e["type"] for e in SEED_EVENTS]
    assert types.count("unlock") >= 6     # Jan-Jun monthly unlocks
    # the June 6 future unlock is present
    assert any("2026-06-06" in e["date"] and e["type"] == "unlock" for e in SEED_EVENTS)


def test_seed_catalog_idempotent(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    n1 = seed_catalog(s)
    n2 = seed_catalog(s)        # second run inserts nothing (dedup by date+type)
    assert n1 == len(SEED_EVENTS)
    assert n2 == 0
    assert len(s.all_events()) == len(SEED_EVENTS)


def test_seed_populates_enrichment(tmp_path):
    s = Store(str(tmp_path / "c.db"))
    seed_catalog(s)
    jun = [e for e in s.all_events() if "Jun" in e["label"]][0]
    assert jun["description"]
    assert "NEAR" in (jun["correlated_assets"] or "")


def test_reseed_backfills_enrichment_on_existing(tmp_path):
    """Events inserted before enrichment existed get refreshed on re-seed."""
    s = Store(str(tmp_path / "c.db"))
    # insert a bare event with no enrichment, matching a catalog entry
    from glory_hype.events.catalog import _to_ms
    ms = _to_ms("2026-06-06")
    s.insert_event({"date_ms": ms, "type": "unlock", "label": "old label",
                    "magnitude_pct": None, "magnitude_usd": None,
                    "source_url": "", "notes": ""})
    seed_catalog(s)   # should UPDATE the existing row with enrichment + fixed label
    row = [e for e in s.all_events() if e["date_ms"] == ms and e["type"] == "unlock"][0]
    assert "Jun" in row["label"]
    assert row["description"]
    assert "NEAR" in (row["correlated_assets"] or "")
