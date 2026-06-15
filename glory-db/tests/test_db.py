"""Tests for the GloryDB durable encrypted store.

Verifies the four properties that matter: it persists, it's encrypted at rest,
it recovers from a crash, and it refuses the wrong key.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "glory-core"))

from glory_db import GloryDB  # noqa: E402
from glory_core import random_bytes  # noqa: E402


@pytest.fixture
def key():
    return random_bytes(32)


def test_put_get(tmp_path, key):
    with GloryDB(tmp_path / "db", key) as db:
        db.put(b"glory", b"is one")
        assert db.get(b"glory") == b"is one"
        assert b"glory" in db
        assert len(db) == 1


def test_get_missing(tmp_path, key):
    with GloryDB(tmp_path / "db", key) as db:
        assert db.get(b"nope") is None


def test_rejects_bad_key_length(tmp_path):
    with pytest.raises(ValueError):
        GloryDB(tmp_path / "db", b"too short")


def test_persistence_across_reopen(tmp_path, key):
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        for i in range(100):
            db.put(i.to_bytes(2, "big"), f"value-{i}".encode())
    # reopen — data must survive
    with GloryDB(path, key) as db:
        assert len(db) == 100
        for i in range(100):
            assert db.get(i.to_bytes(2, "big")) == f"value-{i}".encode()


def test_overwrite_persists(tmp_path, key):
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        db.put(b"k", b"v1")
        db.put(b"k", b"v2")
    with GloryDB(path, key) as db:
        assert db.get(b"k") == b"v2"
        assert len(db) == 1


def test_delete_persists(tmp_path, key):
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        db.put(b"a", b"1")
        db.put(b"b", b"2")
        assert db.delete(b"a") is True
        assert db.delete(b"a") is False
    with GloryDB(path, key) as db:
        assert db.get(b"a") is None
        assert db.get(b"b") == b"2"
        assert len(db) == 1


def test_range_scan(tmp_path, key):
    with GloryDB(tmp_path / "db", key) as db:
        for i in range(50):
            db.put(i.to_bytes(2, "big"), b"x")
        got = [int.from_bytes(k, "big") for k, _ in db.range((10).to_bytes(2, "big"),
                                                              (15).to_bytes(2, "big"))]
        assert got == [10, 11, 12, 13, 14]


def test_encrypted_at_rest(tmp_path, key):
    """The plaintext value must never appear on disk."""
    path = tmp_path / "db"
    secret = b"TOP-SECRET-GLORY-PAYLOAD"
    with GloryDB(path, key) as db:
        db.put(b"classified", secret)
    raw = (path / "wal").read_bytes()
    assert secret not in raw
    assert b"classified" not in raw  # keys are encrypted too


def test_wrong_key_cannot_read(tmp_path, key):
    """A different key must not decrypt the WAL — it recovers as empty."""
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        db.put(b"a", b"secret")
    wrong = random_bytes(32)
    with GloryDB(path, wrong) as db:
        # auth failure on the first record -> treated as torn tail -> empty db
        assert len(db) == 0


def test_crash_recovery_torn_tail(tmp_path, key):
    """A truncated final record (crash mid-append) is discarded; prior data survives."""
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        db.put(b"a", b"1")
        db.put(b"b", b"2")
    # Simulate a crash that left a half-written trailing record.
    wal = path / "wal"
    data = bytearray(wal.read_bytes())
    data.extend(b"\x00\x00\x00\x40")  # claims a 64-byte record that isn't there
    data.extend(b"\xde\xad\xbe\xef")  # only 4 bytes follow
    wal.write_bytes(bytes(data))
    with GloryDB(path, key) as db:
        assert db.get(b"a") == b"1"
        assert db.get(b"b") == b"2"
        assert len(db) == 2


def test_compact_reclaims_and_preserves(tmp_path, key):
    path = tmp_path / "db"
    with GloryDB(path, key) as db:
        for i in range(200):
            db.put(b"k", i.to_bytes(2, "big"))  # 200 overwrites of one key
        for i in range(50):
            db.put(i.to_bytes(2, "big"), b"v")
        for i in range(0, 50, 2):
            db.delete(i.to_bytes(2, "big"))
        size_before = (path / "wal").stat().st_size
        db.compact()
        size_after = (path / "wal").stat().st_size
        assert size_after < size_before  # space reclaimed
        assert db.get(b"k") == (199).to_bytes(2, "big")
        assert len(db) == 1 + 25  # the overwritten key + 25 surviving odds
    # survives reopen after compaction
    with GloryDB(path, key) as db:
        assert db.get(b"k") == (199).to_bytes(2, "big")
        assert len(db) == 26


def test_closed_db_rejects_ops(tmp_path, key):
    db = GloryDB(tmp_path / "db", key)
    db.close()
    with pytest.raises(ValueError):
        db.put(b"a", b"b")


def test_binary_safe(tmp_path, key):
    with GloryDB(tmp_path / "db", key) as db:
        key_b = bytes([0, 255, 0, 10])
        val_b = bytes([0, 0, 255])
        db.put(key_b, val_b)
        assert db.get(key_b) == val_b
