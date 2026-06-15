import os
import pytest

pytestmark = pytest.mark.live


@pytest.mark.skipif(not os.path.exists("hype.db"), reason="needs the real hype.db")
def test_real_sweep_runs():
    from glory_hype.db import Store
    from glory_hype.patterns.backtest import run_backtest
    s = Store("hype.db")
    res = run_backtest(s)
    print(f"events={res['events_detected']} candidates={res.get('candidates')} "
          f"patterns={res['patterns']}")
    for st in s.all_pattern_stats():
        p_val = f"{st['p_value']:.4f}" if st['p_value'] is not None else "None"
        h_lo = f"{st['holdout_lo']:.2f}" if st['holdout_lo'] is not None else "None"
        print(f"  {st['pattern_name']} [{st['source']}] {st['direction']} "
              f"cfg={st['threshold']}%/{st['horizon']}h test_lo={st['win_lo_test']:.2f} "
              f"p={p_val} bh={st['bh_significant']} "
              f"holdout_lo={h_lo} stable={st['stable']}")
    s.close()
