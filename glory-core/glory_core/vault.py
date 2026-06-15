"""Glory Vault — authenticated secret storage.

Upgrades the original AES-256-CBC vault to authenticated encryption
(ChaCha20-Poly1305), so tampering is detected, not silently decrypted. The
encryption key is derived from a passphrase with Argon2id (memory-hard), then
HKDF, so a weak passphrase is far more expensive to brute-force.

File format (all binary, single file):
    magic(8) || argon2_salt(16) || nonce(12) || ciphertext||tag

The passphrase and plaintext secret never touch disk in the clear.
"""

from __future__ import annotations

from pathlib import Path

from argon2.low_level import hash_secret_raw, Type

from glory_core.crypto import encrypt, decrypt, KEY_LEN

_MAGIC = b"GLORYV01"
_SALT_LEN = 16
# Match interactive Argon2id cost from crypto.py.
_TIME_COST = 3
_MEMORY_COST = 64 * 1024
_PARALLELISM = 4


def _derive(passphrase: str, salt: bytes) -> bytes:
    return hash_secret_raw(
        secret=passphrase.encode("utf-8"),
        salt=salt,
        time_cost=_TIME_COST,
        memory_cost=_MEMORY_COST,
        parallelism=_PARALLELISM,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def seal(secret: bytes, passphrase: str, path: str | Path) -> None:
    """Encrypt `secret` under `passphrase` and write it to `path`."""
    import os

    salt = os.urandom(_SALT_LEN)
    key = _derive(passphrase, salt)
    blob = encrypt(key, secret, aad=_MAGIC)
    Path(path).write_bytes(_MAGIC + salt + blob)


def open_vault(passphrase: str, path: str | Path) -> bytes:
    """Decrypt and return the secret. Raises ValueError on wrong passphrase or
    tampered file."""
    data = Path(path).read_bytes()
    if data[:8] != _MAGIC:
        raise ValueError("not a Glory vault file")
    salt = data[8 : 8 + _SALT_LEN]
    blob = data[8 + _SALT_LEN :]
    key = _derive(passphrase, salt)
    return decrypt(key, blob, aad=_MAGIC)
