---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2305.14314"
date: 2026-06-08
tags: [qlora, lora, fine-tuning, quantization, nf4, unsloth, rtx3060, memory-efficiency]
---
# QLoRA: NF4 Quantization + LoRA Adapters for Fine-Tuning on Consumer GPUs

## What
QLoRA (Dettmers et al., 2023) fine-tunes a 4-bit quantized frozen base model by injecting trainable low-rank adapter matrices (in bfloat16) into attention and MLP layers. The base model uses NF4 (NormalFloat4) — an information-theoretically optimal 4-bit quantization for weights with approximately Gaussian distributions — plus Double Quantization (quantizing the quantization constants themselves, saving ~0.37 bits/param). Gradients flow only through the LoRA matrices A and B; the base weights are dequantized on-the-fly during the forward pass: `W_effective = dequantize(W_nf4) + α/r · B×A`.

## Why It Matters
Glory's autoresearch stack runs on an RTX 3060 12GB and unsloth is already installed on D:\. With `load_in_4bit=True` + Unsloth's custom CUDA kernels, a 7B model fits in ~8-10GB VRAM (vs ~15GB in bf16), leaving 2-4GB headroom for batch size > 1. Training 7B on 10K samples takes ~3 hours. Key config knobs:
- **r (rank)**: 16 is the standard starting point; higher = more capacity, more VRAM
- **alpha**: set to r (scaling = 1.0) or 2×r (scaling = 2.0); alpha/r is the effective scale
- **target_modules**: minimum is `q_proj, v_proj`; full coverage adds `k_proj, o_proj, gate_proj, up_proj, down_proj`
- **gradient_checkpointing**: `"unsloth"` mode saves an additional 30% VRAM over standard checkpointing
- **Paged optimizers**: NVIDIA unified memory pages optimizer states to CPU RAM during gradient spikes — prevents OOM on 12GB

This is the path to domain-adapted local models: train a Glory-specific adapter over Gemma/Qwen/Llama, merge with DARE/TIES, quantize to GGUF, deploy in llama.cpp.

## Source
- Primary paper: https://arxiv.org/abs/2305.14314
- Unsloth hyperparameter guide: https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide
- HuggingFace bitsandbytes + 4-bit: https://huggingface.co/blog/4bit-transformers-bitsandbytes

## Connected To
- [[2026-05-26-muon-optimizer]] — alternative optimizer; combine with QLoRA for potentially faster convergence
- [[2026-05-30-model-merging-dare-ties]] — post-fine-tune: merge the adapter into base with DARE/TIES, then re-quantize
- [[2026-06-07-moe-expert-offloading-llama-cpp]] — after merging, deploy the fused model via llama.cpp with MoE offload for inference
- [[2026-05-18-rtx3060-optimal-llm-models]] — VRAM budget reference for the 3060
