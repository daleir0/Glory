"""GloryDB — encrypted, durable, ordered key/value store.

The persistence pillar of Glory. Built on a B+tree index with a glory-core
ChaCha20-Poly1305 write-ahead log. Single directory, no server.

    from glory_db import GloryDB
    from glory_core import random_bytes

    key = random_bytes(32)
    with GloryDB("mydata", key) as db:
        db.put(b"glory", b"is one")
        db.get(b"glory")        # b"is one"
        list(db.range(b"a", b"z"))
"""

from glory_db.db import GloryDB
from glory_db.bptree import BPlusTree

__all__ = ["GloryDB", "BPlusTree"]
__version__ = "0.1.0"
