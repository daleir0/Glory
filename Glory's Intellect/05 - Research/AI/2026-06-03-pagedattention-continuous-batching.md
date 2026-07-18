---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/pdf/2309.06180"
date: 2026-06-03
tags: [inference, vllm, kv-cache, memory, batching, local-inference, throughput]
---
# PagedAttention + Continuous Batching: vLLM's Core Memory Innovation

## What
PagedAttention (SOSP 2023, UC Berkeley) maps each sequence's KV cache through a **logical block table** into non-contiguous **physical blocks** of GPU memory — default 16 tokens per block. Prior systems pre-reserved contiguous KV buffers, wasting 60–80% of GPU memory due to internal fragmentation. PagedAttention reduces waste to under 4%. Combined with continuous batching (scheduler re-evaluates waiting/running/swapped queues after every forward pass), this yields 2–4x throughput over FasterTransformer and Orca at equal latency.

## Why It Matters
On the RTX 3060 (12 GB VRAM), KV cache is the primary constraint for concurrent requests during local inference. Without paged allocation, running even a modest batch of requests on a Qwen-27B or Hermes model forces conservative memory reservation that leaves most of VRAM idle. With PagedAttention-enabled serving (vLLM, llama.cpp continuous batching mode), Glory can serve more concurrent requests from the same GPU — directly increasing throughput for the research pipeline and any future multi-user serving. The copy-on-write prefix sharing also accelerates repeated-prefix prompts (e.g. system prompt reuse across requests).

## Source
- Original paper: https://arxiv.org/pdf/2309.06180
- Explained: https://www.runpod.io/articles/guides/vllm-pagedattention-continuous-batching
- Memory deep-dive: https://datasciencedojo.com/blog/understanding-paged-attention/

## Connected To
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-05-29-kv-cache-quantization]]
- [[hardware/2026-05-18-rtx3060-optimal-llm-models]]
