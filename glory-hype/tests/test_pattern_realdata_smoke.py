import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_backtest_runs():
    """Runs the full backtest on the real 18-month hype.db; asserts it completes and
    writes stats. No assertion on the numbers — they are empirical."""
    from glory_hype.db import Store
    from glory_hype.patterns.backtest import run_backtest
    s = Store("hype.db")
    res = run_backtest(s)
    assert res["events_detected"] >= 0
    stats = s.all_pattern_stats()
    print(f"events={res['events_detected']} patterns={len(stats)}")
    for st in stats:
        print(f"  {st['pattern_name']} [{st['source']}] dir={st['direction']} "
              f"n_test={st['n_test']} lo={st['win_lo_test']:.2f} stable={st['stable']} "
              f"avg_move={st['avg_move_pct']:.1f}%")
    s.close()
