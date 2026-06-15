"""Thin helpers tying the narrative engine to the v1 Store."""

import time


def now_ms() -> int:
    return int(time.time() * 1000)
