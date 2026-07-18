---
type: research-note
domain: AI
confidence: verified
source: "https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/"
date: 2026-06-27
tags: [inference, determinism, reproducibility, rl, kernels, attention, rmsnorm, matmul, sglang, grpo]
---
# Batch-Invariant Kernels: Why LLM Inference Is Nondeterministic and How to Fix It

## What
LLM inference is nondeterministic even at temperature=0 not because of GPU concurrency/atomic races, but because **server batch size varies with load**, and standard kernels (RMSNorm, matmul, attention) change their *reduction order/strategy* depending on batch size. Floating-point addition is non-associative, so a different reduction order yields slightly different logits, which under greedy decoding can flip the argmax and cascade into a different token sequence. The fix (Thinking Machines, Sep 2025) is **batch-invariant kernels**: constrain each reduction op to one universal reduction strategy regardless of batch size, so the same input produces bitwise-identical logits no matter what other requests are co-batched. Their open-source `batch-invariant-ops` PyTorch library gives drop-in RMSNorm/MatMul/Softmax/Attention replacements; 1,000 runs then produce 1,000 identical outputs. SGLang shipped it with FlashInfer/FA3 backends at ~34% slowdown (down from ~61% in earlier work).

## Why It Matters
This is directly load-bearing for Glory's RL work. On-policy RL (our [[2026-06-02-grpo-group-relative-policy-optimization]] setup) assumes the sampler policy == the trainer policy. If the inference engine that generates rollouts is numerically nondeterministic vs. the training forward pass, the importance ratio is silently biased: what should be "on-policy" becomes subtly off-policy, KL drifts, and reward can collapse. Batch-invariant kernels drive the sampler↔trainer KL-divergence to **zero**, giving clean, stable training. Beyond RL it also gives reproducible evals (a benchmark score stops wobbling with server load), reliable regression debugging (a bug reproduces every run), and trustworthy A/B comparisons. The cost is a ~34% throughput hit — so the rule of thumb is: turn determinism ON for RL rollout generation and eval/debug runs, leave it OFF for max-throughput serving where exact reproducibility doesn't matter. The three ops to make batch-invariant are exactly the three reduction-heavy ones: normalization, matmul, and attention (attention needs a fixed split-KV size so the KV reduction order is constant across batch shapes).

## Source
- https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/
- https://www.lmsys.org/blog/2025-09-22-sglang-deterministic/ (SGLang integration, FlashInfer/FA3/Triton backends, ~34% slowdown)
- https://simonwillison.net/2025/Sep/11/defeating-nondeterminism/

## Connected To
- [[2026-06-02-grpo-group-relative-policy-optimization]]
- [[2026-06-04-flash-attention-2-io-optimal-kernel]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[2026-06-25-prefix-caching-radixattention]]
- [[2026-05-29-kv-cache-quantization]]
