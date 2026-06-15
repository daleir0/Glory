"""GloryDB — durable, encrypted key/value store over a B+tree index.

4-Node calibration:
    Fast          — reads/writes hit the in-memory B+tree (O(log n)); WAL append is O(1)
    Decentralized — a plain directory of files; no server, runs anywhere
    Private       — every byte on disk is ChaCha20-Poly1305 ciphertext; no
                    plaintext keys or values ever touch storage
    Secure        — all crypto via glory-core (approved primitives); torn writes
                    from a crash are detected and discarded, never half-applied

Design: the index lives in memory (bptree.py). Durability is an append-only
write-ahead log of encrypted operations. On open the WAL is decrypted and
replayed to rebuild the index. compact() rewrites the WAL as one record per
live key — reclaiming space from overwrites/deletes and flushing the index's
lazy-deleted leaves.

Crash model: an operation is durable once its WAL record is fsync'd. A crash
mid-append leaves a truncated final record; replay detects it (length or auth
failure) and stops — the store recovers to the last fully-written operation.
"""

from __future__ import annotations

import os
import struct
import sys
from pathlib import Path
from typing import Iterator, Optional

# --- bridge to the sibling glory-core building block ----------------------- #
try:
    from glory_core import encrypt, decrypt  # type: ignore
    from glory_core.crypto import KEY_LEN  # type: ignore
except ImportError:  # pragma: no cover - path bootstrap
    _CORE = Path(__file__).resolve().parents[2] / "glory-core"
    sys.path.insert(0, str(_CORE))
    from glory_core import encrypt, decrypt  # type: ignore
    from glory_core.crypto import KEY_LEN  # type: ignore

from glory_db.bptree import BPlusTree

_MAGIC = b"GLORYDB1"
_OP_PUT = 1
_OP_DEL = 2
_LEN = struct.Struct(">I")  # 4-byte big-endian length prefix


def _encode_op(op: int, key: bytes, value: bytes) -> bytes:
    return bytes([op]) + _LEN.pack(len(key)) + key + value


def _decode_op(buf: bytes) -> tuple[int, bytes, bytes]:
    op = buf[0]
    klen = _LEN.unpack(buf[1:5])[0]
    key = buf[5 : 5 + klen]
    value = buf[5 + klen :]
    return op, key, value


class GloryDB:
    """An encrypted, durable, ordered key/value store."""

    def __init__(self, directory: str | Path, key: bytes):
        if len(key) != KEY_LEN:
            raise ValueError(f"key must be {KEY_LEN} bytes")
        self._key = key
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._wal_path = self._dir / "wal"
        self._tree = BPlusTree()
        self._wal = None  # file handle, opened lazily for append
        self._closed = False
        self._replay()

    # ------------------------------------------------------------- durability
    def _replay(self) -> None:
        """Rebuild the in-memory index from the WAL, stopping at any torn tail."""
        if not self._wal_path.exists():
            return
        with open(self._wal_path, "rb") as f:
            data = f.read()
        off = 0
        n = len(data)
        while off + 4 <= n:
            (rec_len,) = _LEN.unpack(data[off : off + 4])
            off += 4
            if off + rec_len > n:
                break  # truncated final record — crash mid-append
            blob = data[off : off + rec_len]
            off += rec_len
            try:
                plain = decrypt(self._key, blob, aad=_MAGIC)
            except ValueError:
                break  # auth failure on tail — torn/garbage, stop here
            op, key, value = _decode_op(plain)
            if op == _OP_PUT:
                self._tree.put(key, value)
            elif op == _OP_DEL:
                self._tree.delete(key)

    def _append(self, op: int, key: bytes, value: bytes) -> None:
        blob = encrypt(self._key, _encode_op(op, key, value), aad=_MAGIC)
        if self._wal is None:
            self._wal = open(self._wal_path, "ab")
        self._wal.write(_LEN.pack(len(blob)))
        self._wal.write(blob)
        self._wal.flush()
        os.fsync(self._wal.fileno())  # durability point

    # ------------------------------------------------------------- public API
    def put(self, key: bytes, value: bytes) -> None:
        self._ensure_open()
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            raise TypeError("keys and values must be bytes")
        self._append(_OP_PUT, key, value)
        self._tree.put(key, value)

    def get(self, key: bytes) -> Optional[bytes]:
        self._ensure_open()
        return self._tree.get(key)

    def delete(self, key: bytes) -> bool:
        self._ensure_open()
        if key not in self._tree:
            return False
        self._append(_OP_DEL, key, b"")
        return self._tree.delete(key)

    def __contains__(self, key: bytes) -> bool:
        return self._tree.get(key) is not None

    def __len__(self) -> int:
        return len(self._tree)

    def items(self) -> Iterator[tuple[bytes, bytes]]:
        self._ensure_open()
        yield from self._tree.items()

    def range(
        self, start: Optional[bytes] = None, end: Optional[bytes] = None
    ) -> Iterator[tuple[bytes, bytes]]:
        self._ensure_open()
        yield from self._tree.range(start, end)

    def compact(self) -> None:
        """Rewrite the WAL as one PUT per live key.

        Reclaims space from overwrites/deletes and rebuilds the index from a
        clean state. Crash-safe: writes to a temp file, fsyncs, then atomically
        replaces the live WAL.
        """
        self._ensure_open()
        if self._wal is not None:
            self._wal.close()
            self._wal = None
        tmp = self._wal_path.with_suffix(".compact")
        with open(tmp, "wb") as f:
            for key, value in self._tree.items():
                blob = encrypt(self._key, _encode_op(_OP_PUT, key, value), aad=_MAGIC)
                f.write(_LEN.pack(len(blob)))
                f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self._wal_path)  # atomic on POSIX and Windows
        # Rebuild the tree so lazy-deleted leaves are dropped.
        self._tree = BPlusTree()
        self._replay()

    def close(self) -> None:
        if self._wal is not None:
            self._wal.flush()
            os.fsync(self._wal.fileno())
            self._wal.close()
            self._wal = None
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise ValueError("database is closed")

    def __enter__(self) -> "GloryDB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
