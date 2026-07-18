---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/pdf/2503.19786"
date: 2026-07-06
tags: [gemma, sliding-window-attention, kv-cache, llama.cpp, local-inference, vram, context]
---
# Gemma's Interleaved Sliding Window Attention (iSWA) and llama.cpp's `--swa-full`

## What
Gemma 3/4 interleave attention layers in a repeating **5 local : 1 global** pattern.
Local layers use a **1024-token sliding window** (each token attends only to the last
1024 tokens); only the 1/6 global layers attend to the full context (up to 128K). Because
just those global layers must cache Keys/Values for the whole sequence, KV-cache memory at
32K context drops from ~60% overhead (global-only) to **under 15%** — with negligible
perplexity impact. llama.cpp implements this as a dual cache (`llama_kv_cache_iswa`): SWA
layers keep only a window-sized cache by default. The **`--swa-full`** flag overrides that,
forcing a full-length KV cache for SWA layers — required for KV-cache reuse / prefix caching
/ context-shift, but it discards the memory savings.

## Why It Matters
Gemma-4-e4b is Hermes' brain (via LM Studio, 127.0.0.1:1234) — this is our live stack.
Two direct consequences on the RTX 3060 (12 GB):
1. **Gemma's KV cache is naturally tiny.** Long-context Gemma sessions cost far less VRAM
   than a same-size global-attention model — budget accordingly; don't over-reserve.
2. **Prefix caching for Gemma is not free.** Reusing a cached prompt prefix across turns
   (the llama-server KV-reuse trick) needs `--swa-full`, which reinflates the KV cache to
   full length. So there's a real trade: cheap memory *or* cross-turn prefix reuse, not both
   for tokens beyond the 1024 window. Below 1024 tokens the flag is a no-op.
   A known LM Studio bug (#1129) is exactly this: missing SWA/context-shift handling balloons
   VRAM because it silently behaves like `--swa-full`.

Rule of thumb for Glory: leave `--swa-full` **off** for cheap long-context Gemma inference;
turn it **on** only when we specifically need prefix/KV reuse and have the VRAM headroom.

## Source
- Gemma 3 Technical Report (5:1 ratio, 1024 window, KV reduction): https://arxiv.org/pdf/2503.19786
- llama.cpp SWA KV cache PR #13194: https://github.com/ggml-org/llama.cpp/pull/13194
- llama-server KV-reuse tutorial (needs `--swa-full`): https://github.com/ggml-org/llama.cpp/discussions/13606
- LM Studio SWA VRAM bug #1129: https://github.com/lmstudio-ai/lmstudio-bug-tracker/issues/1129

## Connected To
- [[2026-07-03-streamingllm-attention-sinks]]
- [[2026-06-26-snapkv-cache-eviction]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-05-18-gemma-4-e4b-architecture]]
- [[2026-05-18-gemma-proxy-integration]]
