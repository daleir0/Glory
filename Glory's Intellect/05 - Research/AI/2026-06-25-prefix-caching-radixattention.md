---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/discussions/20574"
date: 2026-06-25
tags: [inference, kv-cache, prefix-caching, radixattention, llama-cpp, sglang, agentic, ttft]
---
# Prefix Caching: reuse the KV cache of a shared prompt prefix instead of recomputing it

## What
A shared, unchanging prompt prefix (system prompt, tool schemas, a fixed preamble) only needs its KV cache computed **once**. Two engines exploit this:

- **SGLang RadixAttention** — keeps an LRU cache of every request's KV pages inside a **radix tree**. On each new request the scheduler walks the tree, finds the *longest matching prefix*, reuses those attention states, and prefills only the differing suffix. Fully automatic; no prompt engineering. Workloads with 60%+ prefix overlap see 75–95% cache-hit rates and large TTFT drops.
- **llama.cpp `llama-server`** — `cache_prompt: true` is the default; it reuses the KV cache from a prior request when the common prefix matches, prefilling only the changed tail. **Host-memory prompt caching is on by default since Oct 2025**, spilling prefixes to host RAM so prefill on a repeated system prompt can fall from **~60 s to ~200 ms**. Slot matching defaults to a 0.5 similarity threshold; `id_slot` pins a request to a specific slot. `n_cache_reuse` (min chunk for KV-shift reuse) defaults to 0/disabled. (Note: an Oct 2025 regression made cache updates take 80 s+; fixed by mid-May 2026 — keep llama.cpp current.)

## Why It Matters
Every Glory session re-sends an enormous fixed preamble — the Glory Contract, CLAUDE.md, the memory index, tool schemas — before any task-specific tokens. Without prefix caching that whole block is re-prefilled from scratch on the RTX 3060 each turn, dominating time-to-first-token. With it, that KV cache is computed once and reused, so latency tracks only the *new* tokens. This is the single highest-leverage, zero-accuracy-cost win for Glory's repeated-context agentic loops (Hermes/Gemma at localhost:8083, Qwen sessions). Actionable now: confirm `cache_prompt`/host-memory caching is active on our llama.cpp builds, keep the binary past the mid-May-2026 fix, and **order prompts prefix-stable** (fixed preamble first, volatile content last) so the cache actually hits.

## Source
- llama.cpp host-memory prompt caching tutorial: https://github.com/ggml-org/llama.cpp/discussions/20574
- llama.cpp KV cache reuse tutorial: https://github.com/ggml-org/llama.cpp/discussions/13606
- LMSYS RadixAttention blog: https://www.lmsys.org/blog/2024-01-17-sglang/

## Connected To
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-18-claude-prompt-caching]]
- [[2026-05-28-speculative-decoding-local-inference]]
