---
type: research-note
domain: AI
confidence: verified
source: "https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md"
date: 2026-06-29
tags: [inference, speculative-decoding, llama-cpp, mtp, local-inference, vram, throughput]
---
# Multi-Token Prediction (MTP): draft-free speculative decoding now in llama.cpp

## What
Multi-Token Prediction grafts extra output heads onto a transformer that predict the next 2-4 tokens from the *same* shared backbone hidden state. At decode time the runtime drafts a short candidate sequence from these heads in one forward pass, then verifies it against the main distribution and keeps the accepted prefix — the same accept/reject loop as classic speculative decoding, but **with no separate draft model**. DeepSeek-V3 introduced MTP as a training objective (its second-token acceptance is ~85-90%, giving ~1.8× decode throughput). As of llama.cpp PR #22673 (merged 2026-05-16) it ships in main via `--spec-type draft-mtp`, with reported real-world gains of ~1.4×-2.4× (e.g. Qwen3.6 27B Q8_0: 7.4 → 18.1 tok/s on Strix Halo; ~1.73× on RTX PRO 6000 dense).

## Why It Matters
This is the speculative-decoding path that actually fits a 12 GB RTX 3060. Classic draft-model speculation (and EAGLE-3/DFlash) require loading a *second* model into VRAM — the budget Glory does not have. MTP folds the drafter into the main model's own weights, costing only ~2 GB of extra headroom instead of a whole second model, so Glory can get ~1.4-2.2× generation speedup on MTP-native GGUFs (Qwen3.6, Gemma 4, DeepSeek-V3 derivatives) with one model resident. Flags: `--spec-type draft-mtp` plus `--spec-draft-n-max 2` (or 3) — tune n-max to hardware. Caveat: only works with models that were *trained* with MTP heads; the heads add a few GB to the GGUF and acceptance drops on MoE models (~1.17× on a 35B-A3B). This directly upgrades the local-inference stack underpinning Hermes/Gemma and any future Glory-hosted model.

## Source
- llama.cpp speculative docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- DeepSeek-V3 Technical Report (MTP origin, 85-90% accept, 1.8×): https://arxiv.org/pdf/2412.19437
- DataCamp MTP/llama.cpp tutorial (flags, perf): https://www.datacamp.com/tutorial/multi-token-prediction-llama-cpp
- Unsloth MTP model guide: https://unsloth.ai/docs/models/mtp

## Connected To
- [[2026-06-05-eagle-3-speculative-decoding]]
- [[2026-05-28-speculative-decoding-local-inference]]
- [[2026-06-07-moe-expert-offloading-llama-cpp]]
- [[2026-05-18-rtx3060-optimal-llm-models]]
