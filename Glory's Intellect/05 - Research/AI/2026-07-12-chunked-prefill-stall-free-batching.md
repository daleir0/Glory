---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2403.02310"
date: 2026-07-12
tags: [inference, serving, scheduling, throughput, latency, vllm, llama-cpp, batching, ttft, itl]
---
# Chunked Prefill + Stall-Free Batching: piggyback decodes on prefill chunks to break the TTFT/ITL tradeoff

## What
Prefill (processing the whole prompt) is **compute-bound** and runs as one large forward pass; decode (one token per step) is **memory-bandwidth-bound**. A naive scheduler runs a long prefill as a single step, so every in-flight decode request stalls until it finishes — you optimize time-to-first-token (TTFT) at the cost of inter-token latency (ITL) and GPU utilization.

**Chunked prefill** (SARATHI, arXiv 2308.16369; productionized in Sarathi-Serve, OSDI'24) splits a prefill into near-equal-sized chunks and builds **decode-maximal hybrid batches**: each step carries at most one prefill chunk and fills the remaining token budget with decodes. The prefill chunk saturates GPU compute while the decodes **piggyback** at ~an order of magnitude lower marginal cost than a decode-only batch. This is **stall-free batching** — new requests join without ever pausing ongoing decodes. Reported: ~2.6× serving capacity for Mistral-7B on one A100, up to 3.7× for Yi-34B on two A100s vs vLLM; also shrinks pipeline bubbles because every micro-batch has uniform compute.

The single tuning lever in vLLM is `max_num_batched_tokens` (the per-step token budget): **lower (~1024–2048) → smoother ITL / better decode latency**; **higher (4096–8192+) → better prefill throughput / TTFT but decode jitter**. Chunked prefill is now on by default in modern vLLM (default budget is version-dependent — ~2048 in recent versions, 512 in some).

## Why It Matters
Glory increasingly runs **multiple concurrent agents through one endpoint** (Claude + Hermes + overnight research all hitting a local model). Chunked prefill is exactly the mechanism that keeps a long research prompt from freezing an interactive agent's token stream — it's the difference between "one 8K-token prompt hangs the whole server for a second" and "everyone keeps generating smoothly." It's the scheduling layer that sits on top of [[2026-06-03-pagedattention-continuous-batching]] and directly exploits the prefill-vs-decode split quantified in [[2026-07-01-decode-memory-bandwidth-roofline]].

For single-user llama.cpp on the RTX 3060 there are no concurrent decodes to protect, so the full stall-free benefit doesn't apply — but the same lever exists as `-ub` (physical micro-batch / u-batch) and `-b` (logical batch): a big prompt is already processed in `-ub`-sized chunks, and with continuous batching (`--cont-batching`, default) other slots' decodes share the batch. Knowing the tradeoff means tuning `-ub` down when interactive latency matters and up when bulk-ingesting context.

## Source
- Sarathi-Serve (OSDI'24): https://arxiv.org/abs/2403.02310 · https://www.usenix.org/conference/osdi24/presentation/agrawal
- SARATHI (original): https://arxiv.org/abs/2308.16369
- vLLM optimization/tuning docs: https://docs.vllm.ai/en/v0.9.1/configuration/optimization.html

## Connected To
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-07-01-decode-memory-bandwidth-roofline]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-06-04-flash-attention-2-io-optimal-kernel]]
