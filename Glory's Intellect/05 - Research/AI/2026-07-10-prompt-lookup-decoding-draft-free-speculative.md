---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md"
date: 2026-07-10
tags: [speculative-decoding, prompt-lookup, ngram, llama.cpp, vllm, inference-speedup, zero-vram, rag, agentic]
---
# Prompt Lookup (N-gram) Decoding: Draft-Model-Free Speculative Decoding at Zero VRAM Cost

## What
Prompt lookup decoding is speculative decoding with **no draft model**. Instead of a second network proposing tokens, it string-matches the last few generated tokens against n-grams already present in the prompt + prior output, copies the following tokens as the "draft," and verifies them in one batched forward pass of the target model. Matches are accepted; on the first mismatch it falls back to normal sampling. Because verification uses the target model's own logits, **output is bit-identical to greedy/sampled decoding — quality is unchanged**. On input-grounded tasks (RAG, code editing, summarize-then-edit, structured/JSON output) it yields **2×–4× speedup**; when the output reuses nothing from the input there is no speedup and a slight overhead.

- **llama.cpp:** `llama-lookup` tool. Maintains a **hash pool** mapping each n-gram hash → the next token, across three caches — *static* (loaded from a corpus), *dynamic* (persisted and grown across runs, `--lookup-cache-dynamic`), and *context* (built live from tokens generated so far). Drafts up to `--draft-max` tokens per step, verifies, accepts matches, and updates the dynamic cache on exit.
- **vLLM / Aphrodite:** `speculative_config={"method": "ngram", "num_speculative_tokens": 5, "prompt_lookup_min": 2, "prompt_lookup_max": 4}`. Searches for the longest suffix-anchored n-gram match in the recent token buffer.
- If an n-gram cache is combined with a real draft model, the **draftless lookup takes precedence** in llama.cpp.

## Why It Matters
Every speculative-decoding note in this vault so far — [[2026-05-28-speculative-decoding-local-inference]], [[2026-06-05-eagle-3-speculative-decoding]], [[2026-06-29-multi-token-prediction-mtp-llama-cpp]] — buys speed by spending **VRAM**: a draft model, EAGLE heads, or MTP layers all live in memory alongside the target. On Glory's 12 GB RTX 3060 that budget is already contested by the KV cache ([[2026-05-29-kv-cache-quantization]], [[2026-06-26-snapkv-cache-eviction]]) and by MoE offload ([[2026-06-07-moe-expert-offloading-llama-cpp]]). Prompt lookup decoding is the one accelerator that costs **≈0 VRAM** — just a hash table in RAM — so it stacks on top of whatever model already fills the card.

The task profile is a near-perfect fit for Glory's actual workloads. Agentic loops are *maximally* input-grounded: the model re-emits file paths, function names, diffs, tool-call schemas, and quoted context verbatim. That is exactly the "reuses many phrases from the input" regime where lookup wins 2×–4×. Concretely: the autogreen/RP editing passes, GBNF-constrained JSON output ([[2026-05-31-gbnf-grammar-constrained-decoding]]), and any RAG-over-the-vault query decode faster for free, with the target model's distribution preserved (composes cleanly with our sampler stack — [[2026-06-28-min-p-sampling]], [[2026-07-09-top-n-sigma-sampling]] — since verification is against the sampled token, not forced greedy). The persistent dynamic cache also means repeated agent runs get *faster over time* as the n-gram pool learns Glory's recurring phrasing — a compounding win, not a one-shot one. The failure mode is bounded and known: free-form creative generation gets no benefit and a small overhead, so gate it to input-grounded calls.

## Source
- llama.cpp speculative decoding docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- vLLM n-gram speculation: https://docs.vllm.ai/en/latest/features/speculative_decoding/n_gram/
- Original method (apoorvumang/prompt-lookup-decoding): https://github.com/apoorvumang/prompt-lookup-decoding/blob/main/README.md
- llama.cpp ngram cache design (Discussion #4235): https://github.com/ggml-org/llama.cpp/discussions/4235

## Connected To
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-06-05-eagle-3-speculative-decoding]]
- [[2026-06-29-multi-token-prediction-mtp-llama-cpp]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-05-31-gbnf-grammar-constrained-decoding]]
