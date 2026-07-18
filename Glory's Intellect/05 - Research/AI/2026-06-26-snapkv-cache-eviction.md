---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/html/2603.20397v1"
date: 2026-06-26
tags: [kv-cache, inference, long-context, memory-optimization, eviction, snapkv, llama-cpp]
---
# SnapKV: prefill-time KV cache eviction — cut the *number* of cached tokens, orthogonal to quantization

## What
SnapKV compresses the KV cache during **prefill** by dropping unimportant prompt tokens *before* generation starts. It takes a small "observation window" of the last tokens of the prompt, aggregates those queries' attention scores over the preceding prefix to vote for which prefix positions matter, applies **1D pooling** to keep clusters (a high-attention token plus its neighbors, preserving local coherence), then retains only the top-k voted prefix tokens **plus** all observation-window tokens — discarding the rest of the prefix KV. Unlike H2O (which uses a flat cumulative "heavy hitter" score across the full sequence during decode), SnapKV selects per-head with pooled scores, making it more accurate at the same cache budget; it is now a standard prefill-compression baseline. SnapKV++ adds adaptive pooling size and grouped-query-attention (GQA) compatibility.

## Why It Matters
On Glory's 12GB RTX 3060 the KV cache — not weights — is the binding constraint for long context. Eviction is **orthogonal to quantization**: quantization shrinks *bits per cached token* (see [[2026-05-29-kv-cache-quantization]], KIVI-style 2-bit), while eviction shrinks the *count of cached tokens*. They stack multiplicatively: evict the prefix to ~40% of tokens, then quantize bf16→int4, and the cache footprint drops to ~10% with under one point of accuracy loss. For Glory's agentic workloads — large codegraph dumps, research context, long tool transcripts — prefill eviction is the lever that lets a 3060 hold a far longer *effective* context before OOM. Caveat: SnapKV targets the prompt/prefill phase, so it pairs naturally with prefix caching ([[2026-06-25-prefix-caching-radixattention]]) and paged allocation ([[2026-06-03-pagedattention-continuous-batching]]) rather than replacing them.

## Source
- KV Cache Optimization Strategies survey (mechanism, H2O vs SnapKV): https://arxiv.org/html/2603.20397v1
- Top-10 KV Cache Compression techniques (eviction+quant stacking, KIVI): https://www.marktechpost.com/2026/04/29/top-10-kv-cache-compression-techniques-for-llm-inference-reducing-memory-overhead-across-eviction-quantization-and-low-rank-methods/
- RocketKV (SnapKV as stage-1, ICML 2025): https://github.com/NVlabs/RocketKV

## Connected To
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-06-14-a-mem-agentic-memory-zettelkasten]]
