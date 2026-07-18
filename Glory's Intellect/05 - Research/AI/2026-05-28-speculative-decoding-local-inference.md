---
type: research-note
domain: AI
confidence: verified
source: "https://lmstudio.ai/blog/lmstudio-v0.3.10"
date: 2026-05-28
tags: [inference, speculative-decoding, llama-cpp, lm-studio, rtx3060, throughput, kv-cache]
---
# Speculative Decoding: 2–3x Faster Local Inference via Draft-Then-Verify

## What
A small draft model generates N tokens speculatively; the large target model verifies all N in a single parallel forward pass, accepting the longest prefix that matches its own distribution. Because LLM inference is memory-bandwidth-bound (not compute-bound), batching multiple token verifications into one pass amortizes KV cache and weight I/O across many output tokens — producing 2–3x throughput with zero change to output quality. The draft model must share the target's tokenizer and vocabulary; mismatched tokenizers collapse acceptance rate to near zero. Draft model should be ≤5% of target parameter count (e.g. Qwen3 0.6B drafting for Qwen3 8B gives ~1.9x).

## Why It Matters
LM Studio 0.3.10 ships native speculative decoding — no code required, just select a draft model in the UI. The RTX 3060's 12 GB VRAM is sufficient to hold a 0.6B–1B draft model alongside a 7–8B Q4 target. Typical acceptance rates hit 0.75–0.85 on conversational/coding tasks; advanced self-speculative methods (QuantSpec) reach >90%. This is the highest-leverage latency win available on Glory's current hardware without changing models.

llama.cpp flag: `--model-draft <path>` with `llama-speculative` binary. Same feature underlies LM Studio's UI toggle.

Best pairs on Glory's stack:
- Qwen3-0.6B → Qwen3-8B: ~1.9x
- Gemma-3-1B → Gemma-3-12B: ~1.8x

## Source
- https://lmstudio.ai/blog/lmstudio-v0.3.10
- https://vucense.com/dev-corner/speculative-decoding-explained-2x-faster-local-llms-ollama-llama-cpp-2026/
- https://blog.premai.io/speculative-decoding-2-3x-faster-llm-inference-2026/

## Connected To
- [[2026-05-18-kimi-k2-architecture]]
- [[2026-05-18-gemma-4-e4b-architecture]]
- [[rtx3060-optimal-llm-models]]
- [[2026-05-26-muon-optimizer]]
