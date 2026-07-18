# Glory 4-Node Architecture

**Date**: 2026-05-27
**Purpose**: The calibration lens for every Glory project. Every component, every line of code, every dependency is measured against these four nodes.

---

## The Four Nodes

```
              ┌──────────────────────┐
              │       GLORY          │
              │   (every project)    │
              └──────────┬───────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌─────▼─────┐     ┌────▼─────┐    ┌────▼─────┐
   │  FAST   │     │DECENTRAL- │     │ PRIVATE  │    │  SECURE  │
   │         │     │  IZED     │     │          │    │          │
   └─────────┘     └───────────┘     └──────────┘    └──────────┘
```

A change that strengthens one node and weakens another is **not acceptable** unless explicitly justified. The default answer is: improve one without harming any other.

---

## Node 1: FAST

**Definition**: Glory responds at human-perceptible thought-speed. Latency is rude.

**Calibration rules**:
- Hot paths must run in O(1) or O(log n) — no linear scans on user input
- Crypto primitives chosen for speed: ChaCha20 over AES on software targets, Ed25519 over RSA, BLAKE2b over SHA-2
- Caching by default; invalidate on event, not by polling
- I/O is async unless proven otherwise
- Profile before optimizing; never optimize without numbers

**Anti-patterns**:
- Synchronous network calls inside request handlers
- Re-deriving expensive keys per request (cache derived keys per session)
- Loading the whole model/database into memory on every call

---

## Node 2: DECENTRALIZED

**Definition**: No single server, no single account, no single party can break, censor, or surveil Glory. Glory works if any one piece dies.

**Calibration rules**:
- No central authentication server — identity is cryptographic (Ed25519 keypair held by user)
- Data lives where the user runs Glory; replication is opt-in and encrypted
- Glory agents (AI, wallet, database) communicate peer-to-peer where possible
- Code is owned by Glory — no SaaS dependency in the critical path
- Anyone can run a full Glory node; documentation supports that path

**Anti-patterns**:
- Hardcoded API endpoint to a single vendor (Anthropic / OpenAI / AWS) in a core path
- Phone-home telemetry without opt-in
- "Master node" that everyone has to trust

---

## Node 3: PRIVATE

**Definition**: Glory cannot leak what Glory does not know. Data is encrypted before Glory needs to see it; computation is verifiable without exposure.

**Calibration rules**:
- Client-side encryption by default — keys never leave the user
- AEAD everywhere (ChaCha20-Poly1305 / AES-256-GCM) — never raw ciphertext without authentication
- Logs **must not** contain secrets, tokens, signatures, personally identifiable data, or model prompts containing user data
- ZK proofs (zkSTARKs) for "prove without reveal" use cases — identity verification, model inference attestation
- Multi-Party Computation (MPC) for keys that must be split across parties
- No content of user data crosses the network unencrypted, ever

**Anti-patterns**:
- Logging request bodies "for debugging"
- Storing user data plaintext "for indexing"
- Server-side decryption for convenience

---

## Node 4: SECURE

**Definition**: Glory is hardened against tampering, theft, and misuse. Defense in depth — no single layer is the only thing protecting us.

**Calibration rules**:
- Approved cryptographic primitives only (see Glory Security Framework)
- Constant-time comparison for every secret (`secrets.compare_digest`)
- Memory-hard password hashing (Argon2id), never plain hash
- Key hierarchy: Master → KEK → DEK → Session keys
- Every dependency pinned by hash; package firewall on installs
- OWASP Top 10 addressed in every web-facing surface
- Smart contracts pass Slither + Mythril + Echidna pipeline before deploy
- All admin/critical functions guarded by access control + MFA

**Anti-patterns**:
- Home-rolled crypto
- `eval()` / `exec()` on anything that could come from user input
- Secrets in environment variables without vault wrapping
- "We'll add the auth check later"

---

## How Every Glory Component Maps

| Component               | Fast                       | Decentralized          | Private                 | Secure                       |
|-------------------------|----------------------------|------------------------|-------------------------|------------------------------|
| **glory-core**          | BLAKE2b, Ed25519           | No server required     | AEAD by default         | Constant-time, audited prims |
| **Glory Language (gl)** | Bytecode VM, JIT path      | Runs anywhere          | No call-home            | Type system + memory safety  |
| **Glory AI Model**      | Quantized, batched         | Runs locally           | Federated training      | Signed weights               |
| **GLC (Currency)**      | Fast finality (PoA → PoS)  | P2P validator network  | zkSTARK private txns    | Multi-sig governance         |
| **GloryDB**             | B+tree + HNSW, MVCC        | Replication optional   | Encrypted columns       | WAL + integrity checks       |

---

## The Building Block: `glory-core`

The first building block exists. Located at `E:\Glory\glory-core\`, 23/23 tests passing.

It implements:
- **Identity** (Ed25519): wallets, agent identity, code signing
- **AEAD** (ChaCha20-Poly1305): encryption with tamper detection
- **Argon2id**: password hashing
- **HKDF**: key derivation hierarchy (Master → KEK → DEK)
- **BLAKE2b**: content addressing with domain separation
- **Vault**: passphrase-protected secret storage (replaces AES-CBC vault)

Every future Glory project imports from `glory_core`. This is the literal building block — once it exists, the structure is built.

---

## The Discipline

Before writing any new component, ask:

1. **Fast** — what is the worst-case latency? Have I measured it?
2. **Decentralized** — what breaks if my employer / Anthropic / AWS shuts down today?
3. **Private** — what does the network see? What do the logs see?
4. **Secure** — what is the threat model? What is the recovery path?

If any answer is "I don't know", stop and answer it before writing the code.

---

*Calibrated 2026-05-27. Glory is one. The building blocks are real. The structure already exists.*
