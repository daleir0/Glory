# Glory AI — First Steps Research

**Date**: 2026-05-27
**Source**: build-your-own-x, targeted web research
**Status**: Foundation layer — seed knowledge for Glory's four pillars

---

## Pillar 1: Glory AI Model (LLM)

### Primary Resource
- **LLMs-from-scratch** by Sebastian Raschka — https://github.com/rasbt/LLMs-from-scratch
  - The definitive from-scratch GPT implementation in Python/PyTorch
  - Book: *Build a Large Language Model (From Scratch)* (O'Reilly / Manning)

### 7-Chapter Build Roadmap
1. **Understanding LLMs** — concepts, what transformers are
2. **Working with Text Data** — tokenization, BPE tokenizer from scratch
3. **Coding Attention Mechanisms** — self-attention, multi-head attention
4. **Implementing a GPT Model** — full GPT in PyTorch
5. **Pretraining on Unlabeled Data** — training loop, loss, alternative architectures (Llama, Qwen, Gemma)
6. **Finetuning for Classification** — task adaptation
7. **Finetuning for Instruction Following** — RLHF/SFT style

### Minimum Requirements for Glory's Own Model
- Python + PyTorch (can swap PyTorch for a Glory-native framework later)
- Tokenizer (BPE or custom Glory tokenizer)
- Transformer block: embedding → attention → FFN → norm
- Training loop + data pipeline
- Hardware: runs on a laptop; RTX 3060 (what we have) is more than enough

### Additional Resources
- Diffusion models (image gen): https://huggingface.co/learn/diffusion-course/en/unit1/3
- RAG for document search: https://github.com/langchain-ai/rag-from-scratch
- AIToolly GPT guide (2026): https://aitoolly.com/ai-news/article/2026-05-14-building-large-language-models-from-scratch-a-comprehensive-technical-guide-to-gpt-like-architecture

### Glory-Specific AI Design Notes
- Glory's AI must have its own **identity layer** — not just a weights file but a persistent self-model
- Architecture decision pending: decoder-only (GPT-style) vs encoder-decoder
- Long-term: Glory trains on Glory's own data (sessions, research, codebase)
- Glory's model will eventually replace Claude as the primary reasoning engine

---

## Pillar 2: Glory Programming Language

### What We Need to Build
A custom programming language needs four components:
1. **Tokenizer/Lexer** — source code → tokens
2. **Parser** — tokens → AST (Abstract Syntax Tree)
3. **Compiler** (optional initially) — AST → bytecode
4. **Interpreter/VM** — executes bytecode or AST directly

### Key Resources
- *Crafting Interpreters* by Robert Nystrom — https://craftinginterpreters.com (free online, gold standard)
- *Writing A Compiler In Go* by Thorsten Ball — https://compilerbook.com
- Pikuma course (March 2026 update, 27hrs): https://pikuma.com/courses/create-a-programming-language-compiler

### Design Philosophy for Glory Language
- **Semantics-first design**: define what code *means* before designing syntax
- Modern trend: formal methods, correctness as first-class concern (see Lean, Coq)
- Type system options: static vs dynamic, gradual typing, dependent types
- Glory's language should feel *alive* — designed for AI-native programs, not legacy systems
- Consider: whitespace-significant? Symbolic? Readable by non-programmers?

### Possible Glory Language Identity
- Name: `gl` or `gly` or `glory`
- Paradigm: multi-paradigm (functional core, imperative shell)
- First target: interpreted (fast iteration), later compiled to native
- Key feature candidates: built-in async/agents, AI primitives as first-class types

---

## Pillar 3: Glory Currency (GloryCoin / GLC)

### Three Paths
1. **Build a new blockchain from scratch** — maximum control, maximum effort
2. **Fork an existing chain** (Bitcoin/Ethereum fork) — faster, proven security
3. **Launch a token on existing chain** (ERC-20, BNB, Solana SPL) — fastest, least control

### For Glory's Vision: Custom Blockchain
The right choice is path 1 or 2, because Glory needs a currency that is:
- Tied to the Glory AI ecosystem
- Not dependent on external validators
- Designed for AI-agent transactions (micropayments, compute credits)

### Key Resources
- Udemy: Build a Blockchain and Cryptocurrency from Scratch — https://www.udemy.com/course/build-blockchain/
- Built In guide: https://builtin.com/blockchain/create-your-own-blockchain
- DEV: From-scratch vs modern SDKs in 2026 — https://dev.to/thevenice/building-a-blockchain-in-2026-from-scratch-engineering-vs-modern-sdks-34jn

### Core Components to Build
- **Block structure**: hash, previous hash, timestamp, transactions, nonce
- **Consensus mechanism**: PoW (simple) → PoS (efficient) — Glory should use PoS/PoA (Proof of Authority initially)
- **Transaction format**: sender, receiver, amount, signature
- **Wallet**: keypair (private/public), address derivation
- **P2P network**: peer discovery, block propagation
- **Smart contracts** (optional phase 2): programmable transactions

### Glory Currency Design Notes
- Token name: GloryCoin (GLC) — subject to user decision
- Purpose: pay for compute, reward research contributions, AI agent exchange
- Initial supply model: TBD (inflationary vs fixed cap)
- The Glory language will have native GLC transaction primitives

---

## Pillar 4: Glory Database (GloryDB)

### Storage Engine Architecture Choices
| Engine | Best For | Used By |
|--------|----------|---------|
| **B+ Tree** | Read-heavy, range queries | MySQL/InnoDB, MongoDB/WiredTiger |
| **LSM Tree** | Write-heavy, append patterns | Cassandra, Google Bigtable, RocksDB |
| **Hash Index** | Key-value point lookups | Redis |

### Key Resources
- FreeCodeCamp LSM Tree handbook: https://www.freecodecamp.org/news/build-an-lsm-tree-storage-engine-from-scratch-handbook/
- Medium: Writing database storage engine from scratch (Part 1): https://medium.com/@valerii.maslenikov/writing-database-storage-engine-from-scratch-part-1-5303c549c26
- Rust DB engine learnings (2026): https://levelup.gitconnected.com/i-built-a-database-engine-from-scratch-in-rust-heres-what-i-learned-7eadd8679805
- B+ tree deep dive: https://www.hailelagi.com/writing/diy-b-tree/

### AI-Native Database (GloryDB) Requirements
- **Vector storage**: store embeddings natively (not bolt-on like pgvector)
- **Semantic search**: ANN (Approximate Nearest Neighbor) via HNSW indexing
- **ACID transactions**: write-ahead log (WAL), MVCC for concurrency
- **Multimodal**: text, image, audio embeddings in one engine
- **Self-organizing**: Glory's AI can re-index and optimize its own database

### Vector Database Landscape (2026)
Mature players: Pinecone, Weaviate, Milvus, Qdrant, Chroma
- Chroma is "AI-native application database" — closest to what Glory needs
- **GloryDB differentiator**: owned entirely by Glory, stores Glory's own knowledge graph, can be queried in the Glory language

### Components to Build (Phase 1)
1. Key-value store with B+ tree on disk
2. WAL for crash recovery
3. MVCC for concurrent reads/writes
4. Vector column type + HNSW index
5. Query language (subset of Glory language)

---

## Summary: The Stack We're Building

```
┌─────────────────────────────────────────┐
│            GLORY AI MODEL               │
│   (Transformer, trained on Glory data)  │
├─────────────────────────────────────────┤
│          GLORY LANGUAGE (gl)            │
│   (Lexer → Parser → Compiler → VM)     │
├─────────────────────────────────────────┤
│          GLORY DATABASE                 │
│   (B+Tree + WAL + HNSW vectors)        │
├─────────────────────────────────────────┤
│          GLORY CURRENCY (GLC)           │
│   (PoA Blockchain, AI-agent payments)  │
└─────────────────────────────────────────┘
```

**First actual code step**: Build the tokenizer for the Glory language — it's the smallest complete unit and teaches the foundational pattern (text → structured data) that all four pillars share.

---

*Research by Glory (Claude Code). Next: pick Pillar 1 or 2 to start coding.*
