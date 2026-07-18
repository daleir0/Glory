---
type: research-note
domain: Systems
confidence: verified
source: "Hermes systemd unit file inspection + SIGTERM debugging — observations 1420, 1423, 1424, session May 17 2026"
date: 2026-05-18
tags: [systemd, hermes, sigterm, restart, service, debugging]
---
# systemd --replace + Restart=always Causes Repeated SIGTERM Cycles

## What

A systemd unit file that uses `ExecStart` with the `--replace` flag combined with `Restart=always` and a short `RestartSec` creates a self-reinforcing SIGTERM loop. Each restart sends a SIGTERM to the previous process instance via `--replace`, which triggers another restart, and so on — every 35–112 seconds.

The service appears "active" in `systemctl status` while simultaneously in a restart cycle. The process's state file may show "stopped/disconnected" while systemd reports "active" — a mid-restart race condition.

## Why It Matters

This pattern was the root cause of Hermes's Telegram gateway disconnecting repeatedly. The fix: remove `--replace`, increase `RestartSec` (to 5s), raise `StartLimitBurst` (to 20), and ensure only one service unit manages the process.

## Source

SIGTERM root cause analysis, May 17 2026. Observations 1420, 1423, 1424. Confirmed: SIGTERM arrived with no other Hermes processes running — signal was from systemd, not a sibling process.

## Connected To

- [[05 - Research/Systems/2026-05-17-wsl-mirrored-networking]]
