---
type: research-note
domain: systems
confidence: verified
source: "https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod"
date: 2026-07-04
tags: [windows, scheduling, timers, real-time, python, latency]
---
# Windows Timer Resolution: 15.6ms Default Tick, Per-Process Since Win10 2004, Ignored for Background Windows on Win11

## What
Windows quantizes all sleeps and waits to the system timer tick — default ~15.625ms (64 Hz). Three rule changes govern precision today: (1) since Windows 10 2004, `timeBeginPeriod(1)` is per-process, no longer global; (2) since Windows 11, timer resolution requests from minimized/occluded/invisible processes are **ignored** — a backgrounded process silently falls back to ~15.6ms; (3) since Windows 10 1803, `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION` gives ~1ms waits independent of the global tick, and CPython 3.11+ uses it in `time.sleep()` automatically.

Measurement is unaffected: `QueryPerformanceCounter` / Python `time.perf_counter()` stays sub-microsecond regardless. Only *waits* are quantized.

## Why It Matters
GloryV1's autogreen engine does millisecond-precision release timing (RT clock measures round-trip, release lead is tuned in ~10ms steps). A 15.6ms sleep quantum is larger than the entire correction step — if the engine ever relied on coarse `time.sleep()` for pacing, timing error from the scheduler alone would exceed the green window. Two concrete consequences:

1. **We're safe by default**: the stack runs Python 3.12, so `time.sleep()` already uses the high-resolution waitable timer (~1ms). Never downgrade the engine below 3.11 on Windows.
2. **Windows 11 background trap**: any timing-critical process (engine, capture loop, inference server pacing) that gets minimized loses raised timer resolution. Keep the process window visible, or restore global behavior via registry: `HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\kernel` → `GlobalTimerResolutionRequests` (DWORD) = 1.

For sub-millisecond deadlines the robust pattern is hybrid sleep: coarse `sleep(remaining - 2ms)` then spin on `perf_counter()` for the final stretch — the spin burns CPU but is jitter-free.

## Source
- https://learn.microsoft.com/en-us/windows/win32/api/timeapi/nf-timeapi-timebeginperiod (official: per-process scope, background-window exemption)
- https://randomascii.wordpress.com/2020/10/04/windows-timer-resolution-the-great-rule-change/ (Bruce Dawson: Win10 2004 rule change)
- https://github.com/python/cpython/issues/89592 (CPython 3.11 `time.sleep()` → `CREATE_WAITABLE_TIMER_HIGH_RESOLUTION`)

## Connected To
- [[Glory 4-Node Architecture]] — the Fast pillar: latency floors come from the OS, not just the code
- [[2026-06-27-batch-invariant-deterministic-inference]] — same theme: hidden platform nondeterminism below the application layer
- [[windows-hags-gpu-scheduling]] — future note: Hardware-Accelerated GPU Scheduling's effect on CUDA submit latency
