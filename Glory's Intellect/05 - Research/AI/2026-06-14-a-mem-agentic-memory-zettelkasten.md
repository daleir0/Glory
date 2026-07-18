---
type: research-note
domain: AI
confidence: verified
source: "https://arxiv.org/abs/2502.12110"
date: 2026-06-14
tags: [agentic-memory, zettelkasten, llm-agents, memory-architecture, retrieval]
---
# A-MEM: Zettelkasten-Style Dynamic Memory for LLM Agents

## What
A-MEM (NeurIPS 2025, Xu et al.) is a memory architecture for LLM agents that, instead of storing raw conversation/task logs in a fixed schema, has the LLM generate a structured "note" for each new memory (contextual description, keywords, tags), embeds it, and retrieves similar past notes to (1) create bidirectional links where meaningful similarity exists and (2) trigger "memory evolution" — updating the descriptions/tags of older linked notes in light of the new one. There is no predetermined memory schema or fixed operation set; the organization emerges from the agent itself, mirroring the Zettelkasten method of atomic notes + dense linking. It outperformed prior memory baselines (including graph-DB memory systems) across six foundation models.

## Why It Matters
This is almost exactly the structure Glory's `Glory's Intellect/05 - Research/` vault already uses by convention — atomic dated notes with a `## Connected To` section linking related notes — but currently those links are written once at creation time and never revisited. A-MEM's "memory evolution" step is the missing piece: when a new note is written, an agent should re-embed and compare against existing notes, add backlinks where similarity is high, AND go edit the older note's `Connected To`/tags if the new note changes its context (e.g., this note should retroactively get linked from `kv-cache-quantization` and `pagedattention-continuous-batching` notes, and vice versa). Same applies to claude-mem observations — instead of a flat timeline, observations could be embedded and cross-linked into a Zettelkasten graph, making `mem-search`/`smart-explore` retrieval qualitatively better (26% LLM-judge improvement and >90% token savings reported for the related Mem0 system using a similar extract-update-consolidate loop). Concretely actionable: a nightly job that embeds new vault notes, finds top-k similar existing notes, and asks an LLM to propose link/tag updates to both old and new notes.

## Source
https://arxiv.org/abs/2502.12110 (A-MEM: Agentic Memory for LLM Agents, NeurIPS 2025)
Reference implementation: https://github.com/agiresearch/A-mem

## Connected To
- [[2026-05-29-kv-cache-quantization]]
- [[2026-06-03-pagedattention-continuous-batching]]
- [[reference_llm_wiki_pattern]]
