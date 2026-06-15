"""
Autonomous trading daemon — runs autopilot.run_cycle() on a tight loop
without requiring any Claude Code session or user input.

Start:  uv run python daemon.py
Stop:   kill the process (Ctrl+C, or Task Manager)

Logs to daemon.log in the same directory.
"""
import time
import sys
import traceback
import os
import logging
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(__file__), "daemon.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("glory-daemon")

# Base interval in seconds between cycles
BASE_INTERVAL = 150  # 2.5min default
TIGHT_INTERVAL = 90  # 1.5min when momentum detected


def get_interval(last_output: str) -> int:
    """Shorten interval when momentum signals are active."""
    if any(kw in last_output for kw in ["ENTER", "SPIKE", "whale BUY", "whale SELL",
                                         "votes=2", "votes=3", "dip_entry"]):
        return TIGHT_INTERVAL
    return BASE_INTERVAL


def run():
    from autopilot import run_cycle

    log.info("=" * 60)
    log.info("Glory HYPE Daemon started")
    log.info("=" * 60)

    cycle = 0
    while True:
        cycle += 1
        log.info(f"--- Cycle {cycle} ---")

        output_lines = []
        original_print = __builtins__.__dict__["print"] if isinstance(__builtins__, dict) else print

        import builtins
        captured = []

        def capturing_print(*args, **kwargs):
            line = " ".join(str(a) for a in args)
            captured.append(line)
            original_print(*args, **kwargs)

        builtins.print = capturing_print
        try:
            run_cycle()
        except KeyboardInterrupt:
            builtins.print = original_print
            log.info("Daemon stopped by user.")
            break
        except Exception as e:
            builtins.print = original_print
            log.error(f"Cycle error: {e}")
            log.error(traceback.format_exc())
            time.sleep(30)
            continue
        finally:
            builtins.print = original_print

        full_output = "\n".join(captured)
        interval = get_interval(full_output)
        log.info(f"Next cycle in {interval}s")
        time.sleep(interval)


if __name__ == "__main__":
    run()
