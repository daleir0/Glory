---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/pull/9742"
date: 2026-07-13
tags: [sampling, llama-cpp, creativity, truncation, inference, xtc, local-inference]
---
# XTC (Exclude Top Choices) Sampler — Inverted Truncation for Creativity

## What
XTC inverts normal truncation: instead of pruning the *least* likely tokens, it removes the *most* likely ones. With probability `xtc-probability`, it finds every token whose probability is ≥ `xtc-threshold`, then deletes all of them **except the least probable one above the threshold** — so at least one "viable" high-probability token always survives, preserving coherence. Two params: `xtc-probability` (chance of firing per token, default `0.0` = disabled) and `xtc-threshold` (minimum prob to count as a "top" token, default `0.1`; set `1.0` to disable). Merged into llama.cpp via PR #9742 (MaggotHATE); disabled by default like Mirostat and placed outside the normal sampler queue.

## Why It Matters
Glory's sampling toolkit already truncates the *tail* (min-p, top-n-σ) to kill garbage tokens. XTC is the orthogonal lever: it truncates the *head* to break clichés, repetition, and "boring" high-probability continuations — the phrases that are common precisely because they're predictable. For any creative/generative task in Glory's local stack (Gemma/Kimi via llama.cpp), the recommended recipe is **min-p first, then XTC**: `--sampling-seq mx --min-p 0.02 --xtc-probability 0.5`. Min-p removes bad tokens (coherence floor); XTC removes obvious tokens (creativity ceiling). Critical operational note: XTC must NOT be used for deterministic/factual work — removing the argmax token degrades accuracy — so it's a per-task flag, not a global default. Also (issue #9904) beware temperature==0 interactions: XTC placement in the chain matters, since it acts on the probability distribution before greedy selection.

## Source
- PR #9742 "sampling : add XTC sampler" (MaggotHATE): https://github.com/ggml-org/llama.cpp/pull/9742
- llama.cpp completion README (parameter docs + recommended min-p→XTC recipe): https://github.com/ggml-org/llama.cpp/blob/master/tools/completion/README.md
- Edge case — XTC + temperature==0 ordering: https://github.com/ggml-org/llama.cpp/issues/9904

## Connected To
- [[2026-06-28-min-p-sampling]]
- [[2026-07-09-top-n-sigma-sampling]]
- [[2026-05-31-gbnf-grammar-constrained-decoding]]
