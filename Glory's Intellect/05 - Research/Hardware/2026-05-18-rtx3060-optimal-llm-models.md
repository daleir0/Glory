---
type: research-note
domain: Hardware
confidence: verified
source: "craftrigs.com/guides/best-llm-rtx-3060-12gb-vram-2026; modelfit.io/gpu/rtx-3060; knightli.com/en/2026/05/08/rtx-3060-local-llm-models"
date: 2026-05-18
tags: [rtx-3060, vram, local-inference, quantization, gguf, llm, hardware]
---
# RTX 3060 12GB — Optimal Local LLM Models and Quantization (2026)

## What

Glory's primary GPU: **RTX 3060 12GB VRAM**.

**Sweet spot model:** Qwen 2.5 14B at Q4_K_M quantization
- VRAM usage: ~8.5–9GB (leaves 3GB headroom for KV cache)
- Speed: ~30 tok/s

**Speed-optimized:** Llama 3.1 8B Q4_K_M
- ~45 tok/s, 7–8GB VRAM

**Quantization guide:**
| Quantization | Quality | VRAM vs FP16 |
|---|---|---|
| Q4_K_M | Sweet spot — ~75% smaller, minimal quality loss | ~25% of FP16 |
| Q5_K_M | Better quality, slightly larger | ~31% of FP16 |
| Q8 | Near-lossless, close to full precision | ~50% of FP16 |

**Practical VRAM ceiling:** 14B parameters at Q4_K_M fits cleanly. 12B models (Gemma 4's 26B MoE is different — actual activated params are lower) can fit at Q4.

**Speed benchmarks:**
- 8B models: ~42 tok/s
- 13–14B models: ~28–30 tok/s
- RTX 3060 is slower per-token than high-end GPUs but genuinely usable at 7B–14B tier

**Models that currently fit Glory's GPU (2026):**
- Gemma 4 E4B (our current local model — PLE architecture, fits easily)
- Qwen 2.5 14B Q4_K_M (best general reasoning)
- Qwen 2.5 Coder 14B Q4_K_M (best local coding)
- Llama 4 Scout 17B MoE at Q4 (12–16 tok/s)
- DeepSeek-R1 7B (10–12 tok/s, reasoning model)

## Why It Matters

Understanding exactly what fits on the RTX 3060 prevents wasted time loading models that OOM or run too slowly to be useful. Qwen 2.5 14B is the upgrade path from Gemma 4 E4B if Glory needs stronger general reasoning locally. The 3GB KV cache headroom at Q4_K_M means long contexts work without crashing.

## Source

- [Best LLMs for RTX 3060 12GB — CraftRigs](https://craftrigs.com/guides/best-llm-rtx-3060-12gb-vram-2026)
- [RTX 3060 Ollama Models 2026 — modelfit.io](https://modelfit.io/gpu/rtx-3060)

## Connected To

- [[05 - Research/AI/2026-05-18-gemma-4-e4b-architecture]]
- [[05 - Research/AI/2026-05-18-hermes-lmstudio-provider-alias]]
