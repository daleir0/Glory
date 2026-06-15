"""GloryDB B+tree — the ordered index.

4-Node calibration:
    Fast          — O(log n) search/insert/delete; leaves linked for O(k) range scans
    Decentralized — pure data structure, no server, no global state
    Private       — stores only what it is given (encryption handled by the store layer)
    Secure        — no eval, no shared mutable defaults, bounds-checked

This is the in-memory index. Durability, encryption and crash-safety live in
db.py — separation of concerns keeps the tree fast and the store honest.

A B+tree (not a plain B-tree): all values live in the leaves, and leaves are
linked left-to-right so a range scan walks a linked list instead of re-descending
the tree. Keys are bytes (lexicographically ordered); values are arbitrary bytes.
"""

from __future__ import annotations

import bisect
from typing import Iterator, Optional

# Max children per internal node / max values per leaf. Higher = flatter tree,
# fewer hops. 64 is a reasonable default for in-memory nodes.
DEFAULT_ORDER = 64


class _Leaf:
    __slots__ = ("keys", "values", "next")

    def __init__(self) -> None:
        self.keys: list[bytes] = []
        self.values: list[bytes] = []
        self.next: Optional[_Leaf] = None

    def is_leaf(self) -> bool:
        return True


class _Internal:
    __slots__ = ("keys", "children")

    def __init__(self) -> None:
        # len(children) == len(keys) + 1. keys[i] is the smallest key in
        # children[i+1] (the standard B+tree separator invariant).
        self.keys: list[bytes] = []
        self.children: list = []

    def is_leaf(self) -> bool:
        return False


class BPlusTree:
    """An ordered map from bytes keys to bytes values."""

    def __init__(self, order: int = DEFAULT_ORDER) -> None:
        if order < 3:
            raise ValueError("order must be >= 3")
        self.order = order
        self._root = _Leaf()
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: bytes) -> bool:
        return self.get(key) is not None

    # ----------------------------------------------------------------- lookup
    def _find_leaf(self, key: bytes) -> _Leaf:
        node = self._root
        while not node.is_leaf():
            i = bisect.bisect_right(node.keys, key)
            node = node.children[i]
        return node

    def get(self, key: bytes) -> Optional[bytes]:
        """Return the value for key, or None if absent."""
        leaf = self._find_leaf(key)
        i = bisect.bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            return leaf.values[i]
        return None

    # ----------------------------------------------------------------- insert
    def put(self, key: bytes, value: bytes) -> None:
        """Insert or overwrite key -> value."""
        if not isinstance(key, bytes) or not isinstance(value, bytes):
            raise TypeError("keys and values must be bytes")
        split = self._insert(self._root, key, value)
        if split is not None:
            sep_key, right = split
            new_root = _Internal()
            new_root.keys = [sep_key]
            new_root.children = [self._root, right]
            self._root = new_root

    def _insert(self, node, key: bytes, value: bytes):
        """Insert into subtree. Returns (sep_key, new_right_node) if node split."""
        if node.is_leaf():
            i = bisect.bisect_left(node.keys, key)
            if i < len(node.keys) and node.keys[i] == key:
                node.values[i] = value  # overwrite
                return None
            node.keys.insert(i, key)
            node.values.insert(i, value)
            self._size += 1
            if len(node.keys) > self.order:
                return self._split_leaf(node)
            return None

        i = bisect.bisect_right(node.keys, key)
        split = self._insert(node.children[i], key, value)
        if split is None:
            return None
        sep_key, right = split
        node.keys.insert(i, sep_key)
        node.children.insert(i + 1, right)
        if len(node.keys) > self.order:
            return self._split_internal(node)
        return None

    def _split_leaf(self, leaf: _Leaf):
        mid = len(leaf.keys) // 2
        right = _Leaf()
        right.keys = leaf.keys[mid:]
        right.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        right.next = leaf.next
        leaf.next = right
        # In a B+tree the separator is the first key of the right leaf (copied up).
        return right.keys[0], right

    def _split_internal(self, node: _Internal):
        mid = len(node.keys) // 2
        sep_key = node.keys[mid]  # middle key moves up (not copied)
        right = _Internal()
        right.keys = node.keys[mid + 1 :]
        right.children = node.children[mid + 1 :]
        node.keys = node.keys[:mid]
        node.children = node.children[: mid + 1]
        return sep_key, right

    # ----------------------------------------------------------------- delete
    def delete(self, key: bytes) -> bool:
        """Remove key. Returns True if it was present.

        Uses lazy deletion (remove from leaf without rebalancing). Range/point
        queries stay correct; tree may hold under-full leaves until a future
        compaction. This keeps deletes O(log n) and the code small — acceptable
        for GloryDB v1 where the store layer compacts on snapshot.
        """
        leaf = self._find_leaf(key)
        i = bisect.bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            leaf.keys.pop(i)
            leaf.values.pop(i)
            self._size -= 1
            return True
        return False

    # ------------------------------------------------------------------ scans
    def _first_leaf(self) -> _Leaf:
        node = self._root
        while not node.is_leaf():
            node = node.children[0]
        return node

    def items(self) -> Iterator[tuple[bytes, bytes]]:
        """Yield all (key, value) pairs in ascending key order."""
        leaf = self._first_leaf()
        while leaf is not None:
            yield from zip(leaf.keys, leaf.values)
            leaf = leaf.next

    def range(
        self, start: Optional[bytes] = None, end: Optional[bytes] = None
    ) -> Iterator[tuple[bytes, bytes]]:
        """Yield (key, value) for start <= key < end, ascending.

        start=None means from the beginning; end=None means to the end.
        """
        leaf = self._find_leaf(start) if start is not None else self._first_leaf()
        while leaf is not None:
            for k, v in zip(leaf.keys, leaf.values):
                if start is not None and k < start:
                    continue
                if end is not None and k >= end:
                    return
                yield k, v
            leaf = leaf.next
