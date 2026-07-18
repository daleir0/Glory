"""Tests for the GloryDB B+tree index."""

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from glory_db.bptree import BPlusTree  # noqa: E402


def k(n: int) -> bytes:
    """Fixed-width key so bytes order == int order."""
    return n.to_bytes(4, "big")


def test_empty_tree():
    t = BPlusTree()
    assert len(t) == 0
    assert t.get(b"missing") is None
    assert b"missing" not in t
    assert list(t.items()) == []


def test_put_get_single():
    t = BPlusTree()
    t.put(b"key", b"value")
    assert t.get(b"key") == b"value"
    assert b"key" in t
    assert len(t) == 1


def test_overwrite_does_not_grow():
    t = BPlusTree()
    t.put(b"k", b"v1")
    t.put(b"k", b"v2")
    assert t.get(b"k") == b"v2"
    assert len(t) == 1


def test_put_rejects_non_bytes():
    t = BPlusTree()
    with pytest.raises(TypeError):
        t.put("str", b"v")
    with pytest.raises(TypeError):
        t.put(b"k", 123)


def test_order_validation():
    with pytest.raises(ValueError):
        BPlusTree(order=2)


def test_many_inserts_force_splits():
    # order small so we exercise many node splits
    t = BPlusTree(order=4)
    n = 500
    for i in range(n):
        t.put(k(i), k(i * 2))
    assert len(t) == n
    for i in range(n):
        assert t.get(k(i)) == k(i * 2)


def test_items_are_sorted():
    t = BPlusTree(order=4)
    keys = list(range(200))
    random.Random(42).shuffle(keys)
    for i in keys:
        t.put(k(i), k(i))
    out = [key for key, _ in t.items()]
    assert out == sorted(out)
    assert len(out) == 200


def test_range_scan_bounds():
    t = BPlusTree(order=4)
    for i in range(100):
        t.put(k(i), k(i))
    got = [int.from_bytes(key, "big") for key, _ in t.range(k(10), k(20))]
    assert got == list(range(10, 20))  # start inclusive, end exclusive


def test_range_open_ended():
    t = BPlusTree(order=4)
    for i in range(50):
        t.put(k(i), k(i))
    head = [int.from_bytes(key, "big") for key, _ in t.range(end=k(5))]
    assert head == [0, 1, 2, 3, 4]
    tail = [int.from_bytes(key, "big") for key, _ in t.range(start=k(45))]
    assert tail == [45, 46, 47, 48, 49]


def test_delete():
    t = BPlusTree(order=4)
    for i in range(50):
        t.put(k(i), k(i))
    assert t.delete(k(25)) is True
    assert t.get(k(25)) is None
    assert len(t) == 49
    assert t.delete(k(25)) is False  # already gone


def test_delete_preserves_order_and_scan():
    t = BPlusTree(order=4)
    for i in range(100):
        t.put(k(i), k(i))
    for i in range(0, 100, 2):  # delete evens
        t.delete(k(i))
    remaining = [int.from_bytes(key, "big") for key, _ in t.items()]
    assert remaining == list(range(1, 100, 2))


def test_stress_random_ops_match_dict():
    """Differential test: B+tree must behave like a sorted dict."""
    t = BPlusTree(order=8)
    ref: dict[bytes, bytes] = {}
    rng = random.Random(7)
    for _ in range(3000):
        key = k(rng.randint(0, 200))
        if rng.random() < 0.7:
            val = bytes([rng.randint(0, 255)])
            t.put(key, val)
            ref[key] = val
        else:
            t.delete(key)
            ref.pop(key, None)
    assert len(t) == len(ref)
    assert dict(t.items()) == ref
    assert [key for key, _ in t.items()] == sorted(ref)


def test_binary_safe_keys_and_values():
    t = BPlusTree()
    key = bytes([0, 255, 10, 0])
    val = bytes([0, 0, 0])
    t.put(key, val)
    assert t.get(key) == val
