---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/discussions/5932"
date: 2026-05-29
tags: [kv-cache, quantization, local-inference, vram, llama.cpp, flash-attention, kivi]
---
# KV Cache Quantization: Keys Tolerate Low Bits, Values Do Not

## What
The KV cache (per-token key/value tensors retained across the context window) can be quantized independently of model weights to fit longer context in VRAM. In llama.cpp, FP16→Q8_0 roughly halves cache size for <0.1% perplexity loss; Q4_0 saves ~72% but degrades asymmetrically — Q4 on the **K-cache costs ~0.4% perplexity, Q4 on the V-cache costs ~1.4%** (3–4× worse). The reason (from KIVI/KVQuant): keys have a few fixed channels with large outlier magnitudes, so keys should be quantized **per-channel**; values lack that pattern and quantize cleanly **per-token**. Practical rule: **Q8_0 always; Q4 keys only when desperate; Q4 values rarely.**

## Why It Matters
Glory runs local inference on a 12 GB RTX 3060 where context length, not weights, is the VRAM bottleneck at long contexts. Q8_0 KV cache is nearly free quality-wise and immediately roughly doubles the context that fits — directly enabling longer agentic memory and bigger prompts for Gemma/Kimi via the proxy. Critical implementation detail: **only symmetric KV quantization (e.g. Q8_0 keys + Q8_0 values) keeps the fused Flash Attention kernel**; asymmetric configs (Q4 keys + F16 values) fall off the fast path and lose speed. So the actionable setting is `--cache-type-k q8_0 --cache-type-v q8_0 --flash-attn` — never mix precisions if throughput matters.

## Source
- https://github.com/ggml-org/llama.cpp/discussions/5932 (4-bit KV cache discussion)
- https://github.com/ggml-org/llama.cpp/discussions/22411 (symmetric quant → fused Flash Attention path)
- https://arxiv.org/abs/2402.02750 (KIVI: per-channel keys, per-token values, asymmetric 2-bit)
- https://www.techplained.com/kv-cache-quantization (Q8 vs FP16, Q4 pitfalls)

## Connected To
- [[2026-05-18-rtx3060-optimal-llm-models]]
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-05-18-gemma-4-e4b-architecture]]
- [[2026-05-18-kimi-k2-architecture]]
