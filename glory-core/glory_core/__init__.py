"""glory-core — Glory's foundational security primitives.

The shared building block for all four pillars (AI model, language, currency,
database). Every cryptographic operation in Glory routes through here so the
approved-primitive policy is enforced in exactly one place.

Four-node calibration:
    Fast        — primitives chosen for speed (ChaCha20, BLAKE2, Ed25519)
    Decentralized — no servers required; keys live with the holder
    Private     — authenticated encryption, no plaintext at rest
    Secure      — constant-time ops, no home-rolled crypto
"""

from glory_core.crypto import (
    Identity,
    encrypt,
    decrypt,
    hash_password,
    verify_password,
    derive_key,
    random_bytes,
    constant_time_equal,
    secure_hash,
)

__all__ = [
    "Identity",
    "encrypt",
    "decrypt",
    "hash_password",
    "verify_password",
    "derive_key",
    "random_bytes",
    "constant_time_equal",
    "secure_hash",
]

__version__ = "0.1.0"
