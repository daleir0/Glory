import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_event_study():
    """Seed the real catalog, study past unlocks/ETFs against hype.db, print the playbook
    and the June 6 forward alert. No correctness assertion on the numbers (empirical)."""
    import time
    from glory_hype.db import Store
    from glory_hype.events.catalog import seed_catalog
    from glory_hype.events.upcoming import analyze_events, upcoming_events
    s = Store("hype.db")
    print("seeded:", seed_catalog(s))
    res = analyze_events(s)
    for t, c in res["types"].items():
        print(f"  {t}: {c['confidence_label']} pre={c['median_pre']} post={c['median_post']} "
              f"trough={c['median_trough']} peak={c['median_peak']}")
    print("UPCOMING:")
    for e in upcoming_events(s, int(time.time() * 1000), 30):
        print(f"  {e['label']} in {e['days_until']}d proximity={e['proximity']} "
              f"hist_n={e['composite'].get('n')}")
    s.close()
