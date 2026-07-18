---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2309.17453"
date: 2026-07-03
tags: [kv-cache, attention-sinks, streamingllm, llama-cpp, context-management, agentic-memory]
---
# StreamingLLM: Attention Sinks Enable Unbounded-Length Generation Without Fine-Tuning

## What
Softmax attention forces scores to sum to 1 across all tokens, so models learn to dump disproportionate attention onto the first few tokens of a sequence regardless of their semantic content — these become "attention sinks." StreamingLLM (Xiao et al., ICLR 2024) exploits this: it keeps a small fixed set of initial tokens (as few as 4) permanently in the KV cache alongside a sliding window of the most recent tokens, discarding everything in between and re-deriving positions relative to the cache rather than the original sequence. This keeps attention score distributions stable and lets a model trained on a finite window (e.g. 4K) generate coherently for millions of tokens with zero fine-tuning. llama.cpp implements the same mechanic in its server via `--keep`/`n_keep`: when context fills, it retains the first `n_keep` prompt tokens as a sink, discards the oldest half of the remainder, and shifts — this is "context shift," disabled with `--no-context-shift`.

## Why It Matters
Every long-running Glory agent process — the Hermes Telegram bot, the overnight autoresearch loop, Glory Rooms multi-model conversations — eventually fills its context window. Without a sink strategy the naive fallback is either truncate-and-lose-coherence or hard-stop generation. `n_keep` in llama.cpp is already sitting there as a StreamingLLM-style rolling cache, but it's config, not automatic: if `n_keep` is left at the default (0), the model loses ALL early context including system prompt on every context-shift event, which is a likely silent cause of a long-running Hermes session drifting off its instructions after enough turns. Setting `n_keep` to cover the system prompt + a few anchor tokens is a one-line config change that buys unbounded conversation length with stable behavior — directly relevant wherever Gemma/Qwen are served locally for persistent sessions.

## Source
https://arxiv.org/abs/2309.17453 (StreamingLLM paper, ICLR 2024)
https://github.com/mit-han-lab/streaming-llm
https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md (`--keep`/`n_keep`, `--no-context-shift`)

## Connected To
- [[2026-06-26-snapkv-cache-eviction]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-05-29-kv-cache-quantization]]
- [[2026-07-01-decode-memory-bandwidth-roofline]]
