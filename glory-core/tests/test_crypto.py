"""Tests for glory_core — verifies every primitive does what the framework promises."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from glory_core import (  # noqa: E402
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
from glory_core import vault  # noqa: E402


# --------------------------------------------------------------------------- #
# Randomness & utilities
# --------------------------------------------------------------------------- #
def test_random_bytes_length_and_uniqueness():
    assert len(random_bytes(32)) == 32
    assert random_bytes(16) != random_bytes(16)


def test_random_bytes_rejects_nonpositive():
    with pytest.raises(ValueError):
        random_bytes(0)


def test_constant_time_equal():
    assert constant_time_equal(b"secret", b"secret")
    assert not constant_time_equal(b"secret", b"secre_")


def test_secure_hash_is_deterministic_and_domain_separated():
    assert secure_hash(b"data") == secure_hash(b"data")
    assert len(secure_hash(b"data")) == 32
    # Same input, different domain -> different hash.
    assert secure_hash(b"data", person=b"a") != secure_hash(b"data", person=b"b")


# --------------------------------------------------------------------------- #
# AEAD
# --------------------------------------------------------------------------- #
def test_encrypt_decrypt_roundtrip():
    key = random_bytes(32)
    msg = b"Glory is private."
    assert decrypt(key, encrypt(key, msg)) == msg


def test_encrypt_is_nondeterministic():
    key = random_bytes(32)
    assert encrypt(key, b"x") != encrypt(key, b"x")  # random nonce each time


def test_decrypt_rejects_tampered_ciphertext():
    key = random_bytes(32)
    blob = bytearray(encrypt(key, b"hello"))
    blob[-1] ^= 0x01  # flip a bit in the tag
    with pytest.raises(ValueError):
        decrypt(key, bytes(blob))


def test_decrypt_rejects_wrong_key():
    blob = encrypt(random_bytes(32), b"hello")
    with pytest.raises(ValueError):
        decrypt(random_bytes(32), blob)


def test_aad_binding():
    key = random_bytes(32)
    blob = encrypt(key, b"hello", aad=b"record-1")
    assert decrypt(key, blob, aad=b"record-1") == b"hello"
    with pytest.raises(ValueError):
        decrypt(key, blob, aad=b"record-2")  # wrong context rejected


def test_encrypt_rejects_bad_key_length():
    with pytest.raises(ValueError):
        encrypt(b"short", b"data")


# --------------------------------------------------------------------------- #
# Key derivation
# --------------------------------------------------------------------------- #
def test_derive_key_deterministic_and_context_separated():
    master = random_bytes(32)
    assert derive_key(master, "kek/db") == derive_key(master, "kek/db")
    assert derive_key(master, "kek/db") != derive_key(master, "kek/wallet")
    assert len(derive_key(master, "x")) == 32


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def test_password_hash_verify():
    h = hash_password("correct horse battery staple")
    assert verify_password(h, "correct horse battery staple")
    assert not verify_password(h, "wrong password")


def test_password_hash_is_salted():
    assert hash_password("same") != hash_password("same")


def test_verify_password_handles_garbage_hash():
    assert not verify_password("not-a-real-hash", "anything")


# --------------------------------------------------------------------------- #
# Identity (Ed25519)
# --------------------------------------------------------------------------- #
def test_identity_sign_verify():
    ident = Identity.generate()
    msg = b"transfer 10 GLC"
    sig = ident.sign(msg)
    assert Identity.verify(ident.public_key_bytes, msg, sig)


def test_identity_rejects_tampered_message():
    ident = Identity.generate()
    sig = ident.sign(b"transfer 10 GLC")
    assert not Identity.verify(ident.public_key_bytes, b"transfer 99 GLC", sig)


def test_identity_from_seed_is_deterministic():
    seed = random_bytes(32)
    a, b = Identity.from_seed(seed), Identity.from_seed(seed)
    assert a.public_key_bytes == b.public_key_bytes
    assert a.address == b.address


def test_identity_seed_validation():
    with pytest.raises(ValueError):
        Identity.from_seed(b"too short")


def test_address_format():
    addr = Identity.generate().address
    assert addr.startswith("glory1")
    assert len(addr) == len("glory1") + 40  # 20 bytes hex


def test_verify_rejects_garbage_pubkey():
    assert not Identity.verify(b"bad", b"msg", b"sig")


# --------------------------------------------------------------------------- #
# Vault
# --------------------------------------------------------------------------- #
def test_vault_seal_open_roundtrip(tmp_path):
    p = tmp_path / "secret.glory"
    vault.seal(b"sk-glory-api-key", "strong-passphrase", p)
    assert vault.open_vault("strong-passphrase", p) == b"sk-glory-api-key"


def test_vault_wrong_passphrase_fails(tmp_path):
    p = tmp_path / "secret.glory"
    vault.seal(b"top secret", "right", p)
    with pytest.raises(ValueError):
        vault.open_vault("wrong", p)


def test_vault_detects_tampering(tmp_path):
    p = tmp_path / "secret.glory"
    vault.seal(b"top secret", "pass", p)
    data = bytearray(p.read_bytes())
    data[-1] ^= 0x01
    p.write_bytes(bytes(data))
    with pytest.raises(ValueError):
        vault.open_vault("pass", p)
