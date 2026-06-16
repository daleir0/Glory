---
type: research-note
domain: Systems
confidence: verified
source: "WSL .wslconfig investigation — observations 1394, 1395, 1396, session May 17 2026"
date: 2026-05-18
tags: [wsl, networking, mirrored, localhost, lm-studio, hermes]
---
# WSL Mirrored Networking: localhost Works, LAN IP Does Not

## What

With WSL2 mirrored networking mode enabled (via `.wslconfig`), `localhost` and `127.0.0.1` from inside WSL resolve correctly to the Windows host. However, the machine's LAN IP (e.g., `192.168.0.31`) does **not** work from inside WSL for reaching Windows services.

Practical consequence: Hermes's `base_url` for LM Studio must be set to `http://127.0.0.1:1234`, not `http://192.168.0.31:1234` or any link-local IP.

## Why It Matters

This caused Hermes to be unreachable to LM Studio until the config was corrected. The fix (observation 1396): change `base_url` in Hermes config from the link-local/LAN IP to `localhost`. After this fix, Hermes gateway achieved 90-second stable uptime — the longest in the debugging session.

## Source

WSL network investigation and Hermes config fix, May 17 2026. Observations 1394, 1395, 1396. `.wslconfig` in Windows home directory controls mirrored networking mode.

## Connected To

- [[05 - Research/Systems/2026-05-17-wsl-no-resolv-conf]]
- [[05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field]]
