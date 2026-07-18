---
type: research-note
domain: Systems
confidence: verified
source: "WSL network investigation — observation 1394, session May 17 2026"
date: 2026-05-18
tags: [wsl, networking, dns, lm-studio, resolv-conf]
---
# WSL Has No resolv.conf — LM Studio Port 1234 Unreachable from WSL

## What

In Glory's WSL2 setup, there is no `/etc/resolv.conf` file. As a result, DNS resolution inside WSL may behave unexpectedly. Additionally, LM Studio running on port 1234 of the Windows host is **not reachable** from inside WSL via the LAN IP (192.168.0.31). It is only reachable via `localhost` / `127.0.0.1` when WSL mirrored networking is configured.

## Why It Matters

Any process running inside WSL (e.g., Hermes) that tries to reach LM Studio must use `127.0.0.1:1234`, not the machine's LAN IP. Using the LAN IP will cause connection failures even though LM Studio is running.

## Source

WSL network investigation, May 17 2026. Observations 1394, 1395. Confirmed by TCP test: `127.0.0.1:1234` accepts connection, `192.168.0.31:1234` does not.

## Connected To

- [[05 - Research/Systems/2026-05-17-wsl-mirrored-networking]]
- [[05 - Research/AI/2026-05-18-lm-studio-reasoning-content-field]]
