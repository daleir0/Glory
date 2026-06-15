"""Glory's approved cryptographic primitives.

Policy (see Glory Security Framework):
    Signatures      Ed25519
    AEAD            ChaCha20-Poly1305
    Password hash   Argon2id
    Key derivation  HKDF-SHA256
    Content hash    BLAKE2b
    Randomness      os.urandom (CSPRNG)

Forbidden anywhere in Glory: MD5, SHA-1, ECB, DES, RC4, home-rolled crypto.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidTag, InvalidSignature

_NONCE_LEN = 12  # ChaCha20-Poly1305 nonce
KEY_LEN = 32  # 256-bit keys everywhere

# Argon2id tuned for interactive auth: memory-hard, resists GPU cracking.
_ph = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=4)


# --------------------------------------------------------------------------- #
# Randomness & comparison
# --------------------------------------------------------------------------- #
def random_bytes(n: int) -> bytes:
    """Cryptographically secure random bytes."""
    if n <= 0:
        raise ValueError("n must be positive")
    return os.urandom(n)


def constant_time_equal(a: bytes, b: bytes) -> bool:
    """Timing-attack-resistant comparison. Use for all secret comparisons."""
    return hmac.compare_digest(a, b)


def secure_hash(data: bytes, *, person: bytes = b"") -> bytes:
    """BLAKE2b-256 content hash. `person` domain-separates hashes by use
    (e.g. b"glory-block" vs b"glory-tx") so the same bytes can't collide
    across contexts."""
    return hashlib.blake2b(data, digest_size=32, person=person[:16]).digest()


# --------------------------------------------------------------------------- #
# Authenticated encryption (ChaCha20-Poly1305)
# --------------------------------------------------------------------------- #
def encrypt(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Encrypt with ChaCha20-Poly1305. Returns nonce || ciphertext||tag.

    `aad` (additional authenticated data) is authenticated but not encrypted —
    bind ciphertext to context (record id, block height) to stop swap attacks.
    """
    if len(key) != KEY_LEN:
        raise ValueError(f"key must be {KEY_LEN} bytes")
    nonce = os.urandom(_NONCE_LEN)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, aad)
    return nonce + ct


def decrypt(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """Reverse of `encrypt`. Raises ValueError on tamper/wrong key."""
    if len(key) != KEY_LEN:
        raise ValueError(f"key must be {KEY_LEN} bytes")
    if len(blob) < _NONCE_LEN:
        raise ValueError("ciphertext too short")
    nonce, ct = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    try:
        return ChaCha20Poly1305(key).decrypt(nonce, ct, aad)
    except InvalidTag as exc:
        raise ValueError("decryption failed: wrong key or tampered data") from exc


# --------------------------------------------------------------------------- #
# Key derivation (HKDF) — powers the Master -> KEK -> DEK hierarchy
# --------------------------------------------------------------------------- #
def derive_key(master: bytes, context: str, length: int = KEY_LEN) -> bytes:
    """Derive a sub-key from a master key for a named context.

    Same (master, context) always yields the same key; different contexts yield
    independent keys. This is how Glory builds its key hierarchy without storing
    every key.
    """
    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=None,
        info=context.encode("utf-8"),
    ).derive(master)


# --------------------------------------------------------------------------- #
# Password hashing (Argon2id)
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    """Hash a password with Argon2id. Returns an encoded string (params + salt
    included) safe to store."""
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    """Verify a password against a stored Argon2id hash. Never raises on
    mismatch — returns False."""
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


# --------------------------------------------------------------------------- #
# Identity (Ed25519) — Glory wallets, agent identity, code signing
# --------------------------------------------------------------------------- #
class Identity:
    """An Ed25519 keypair: a Glory identity.

    Used for GLC wallet addresses, agent-to-agent authentication, and signing
    blocks/transactions. Deterministic from a 32-byte seed so a wallet can be
    restored from a backed-up seed.
    """

    __slots__ = ("_private",)

    def __init__(self, private_key: Ed25519PrivateKey):
        self._private = private_key

    @classmethod
    def generate(cls) -> "Identity":
        """Create a fresh random identity."""
        return cls(Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: bytes) -> "Identity":
        """Reconstruct an identity from a 32-byte seed (deterministic)."""
        if len(seed) != 32:
            raise ValueError("seed must be 32 bytes")
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    def sign(self, message: bytes) -> bytes:
        """Sign a message. Returns a 64-byte signature."""
        return self._private.sign(message)

    @property
    def public_key_bytes(self) -> bytes:
        """Raw 32-byte public key."""
        from cryptography.hazmat.primitives import serialization

        return self._private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    @property
    def address(self) -> str:
        """Glory address: 'glory1' + first 20 bytes of BLAKE2b(pubkey), hex.

        Short, collision-resistant fingerprint of the public key — what a GLC
        wallet shows and what a transaction references.
        """
        digest = secure_hash(self.public_key_bytes, person=b"glory-addr")
        return "glory1" + digest[:20].hex()

    @staticmethod
    def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
        """Verify a signature against a raw 32-byte public key. Returns False
        on any failure (never raises)."""
        try:
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
            return True
        except (InvalidSignature, ValueError):
            return False
