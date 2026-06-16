"""SQLite store for HYPE market data. WAL mode so the read-only server can
query concurrently while the collector writes."""

import json
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    interval TEXT NOT NULL,
    open_ts  INTEGER NOT NULL,
    close_ts INTEGER NOT NULL,
    o REAL, h REAL, l REAL, c REAL, v REAL, n INTEGER,
    PRIMARY KEY (interval, open_ts)
);
CREATE TABLE IF NOT EXISTS market_ctx (
    ts INTEGER PRIMARY KEY,
    funding REAL, open_interest REAL, mark_px REAL, oracle_px REAL,
    mid_px REAL, premium REAL, prev_day_px REAL, day_ntl_vlm REAL
);
CREATE TABLE IF NOT EXISTS trades (
    tid INTEGER PRIMARY KEY,
    ts INTEGER NOT NULL, px REAL, sz REAL, side TEXT, ntl REAL,
    is_large INTEGER
);
CREATE TABLE IF NOT EXISTS book_snapshots (
    ts INTEGER PRIMARY KEY,
    bids_json TEXT, asks_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_ts ON trades(ts);
CREATE INDEX IF NOT EXISTS idx_trades_large ON trades(is_large, ts);
CREATE TABLE IF NOT EXISTS narrative_items (
    hash TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    source TEXT NOT NULL,
    reliability_weight REAL,
    title TEXT,
    body TEXT,
    url TEXT
);
CREATE INDEX IF NOT EXISTS idx_narr_ts ON narrative_items(ts);
CREATE INDEX IF NOT EXISTS idx_narr_source ON narrative_items(source);
CREATE TABLE IF NOT EXISTS narrative_conclusions (
    generated_at INTEGER PRIMARY KEY,
    json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chart_reads (
    ts INTEGER PRIMARY KEY,
    timeframe TEXT,
    trend TEXT,
    current_price REAL,
    image_path TEXT,
    status TEXT NOT NULL DEFAULT 'read',
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chart_ts ON chart_reads(ts);
CREATE INDEX IF NOT EXISTS idx_chart_trend ON chart_reads(trend);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS trade_calls (
    generated_at INTEGER PRIMARY KEY,
    decision TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_calls_ts ON trade_calls(generated_at);
CREATE INDEX IF NOT EXISTS idx_calls_status ON trade_calls(status);
CREATE TABLE IF NOT EXISTS regimes (
    ts INTEGER, timeframe TEXT, label TEXT, features_json TEXT,
    PRIMARY KEY (ts, timeframe)
);
CREATE TABLE IF NOT EXISTS pattern_events (
    ts INTEGER, pattern_name TEXT, source TEXT, direction TEXT, features_json TEXT,
    fwd_4h REAL, fwd_12h REAL, fwd_24h REAL,
    PRIMARY KEY (ts, pattern_name)
);
CREATE TABLE IF NOT EXISTS pattern_stats (
    pattern_name TEXT PRIMARY KEY, source TEXT, n_train INTEGER, n_test INTEGER,
    win_rate_train REAL, win_lo_test REAL, win_hi_test REAL,
    avg_move_pct REAL, avg_move_hrs REAL, direction TEXT, stable INTEGER,
    threshold REAL, horizon INTEGER, p_value REAL, bh_significant INTEGER,
    holdout_lo REAL, n_holdout INTEGER
);
CREATE TABLE IF NOT EXISTS discovered_patterns (
    name TEXT PRIMARY KEY, centroid_json TEXT, dominant_features_json TEXT, created_at INTEGER
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_ms INTEGER, type TEXT, label TEXT, magnitude_pct REAL,
    magnitude_usd REAL, source_url TEXT, notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_date ON events(date_ms);
CREATE TABLE IF NOT EXISTS event_studies (
    type TEXT PRIMARY KEY, n INTEGER, median_pre REAL, median_post REAL,
    median_trough REAL, median_peak REAL, spread_json TEXT,
    confidence_label TEXT, computed_at INTEGER
);
"""


class Store:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA wal_autocheckpoint=2000")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        cols = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(chart_reads)").fetchall()]
        if "status" not in cols:
            self.conn.execute(
                "ALTER TABLE chart_reads ADD COLUMN status TEXT NOT NULL DEFAULT 'read'")
        cols2 = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(trade_calls)").fetchall()]
        if cols2 and "status" not in cols2:
            self.conn.execute(
                "ALTER TABLE trade_calls ADD COLUMN status TEXT NOT NULL DEFAULT 'open'")
        pcols = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(pattern_stats)").fetchall()]
        for col, decl in [("threshold", "REAL"), ("horizon", "INTEGER"),
                          ("p_value", "REAL"), ("bh_significant", "INTEGER"),
                          ("holdout_lo", "REAL"), ("n_holdout", "INTEGER")]:
            if pcols and col not in pcols:
                self.conn.execute(f"ALTER TABLE pattern_stats ADD COLUMN {col} {decl}")
        ecols = [r["name"] for r in self.conn.execute(
            "PRAGMA table_info(events)").fetchall()]
        for col, decl in [("description", "TEXT"), ("correlated_assets", "TEXT")]:
            if ecols and col not in ecols:
                self.conn.execute(f"ALTER TABLE events ADD COLUMN {col} {decl}")

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    def insert_candle(self, c: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT INTO candles (interval, open_ts, close_ts, o, h, l, c, v, n)
                   VALUES (:interval, :open_ts, :close_ts, :o, :h, :l, :c, :v, :n)
                   ON CONFLICT(interval, open_ts) DO UPDATE SET
                     close_ts=excluded.close_ts, o=excluded.o, h=excluded.h,
                     l=excluded.l, c=excluded.c, v=excluded.v, n=excluded.n""",
                c,
            )
            self.conn.commit()

    def insert_ctx(self, ctx: dict, ts: int) -> None:
        row = {**ctx, "ts": ts}
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO market_ctx
                   (ts, funding, open_interest, mark_px, oracle_px, mid_px, premium,
                    prev_day_px, day_ntl_vlm)
                   VALUES (:ts, :funding, :open_interest, :mark_px, :oracle_px, :mid_px,
                           :premium, :prev_day_px, :day_ntl_vlm)""",
                row,
            )
            self.conn.commit()

    def insert_trade(self, t: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR IGNORE INTO trades (tid, ts, px, sz, side, ntl, is_large)
                   VALUES (:tid, :ts, :px, :sz, :side, :ntl, :is_large)""",
                {**t, "is_large": 1 if t["is_large"] else 0},
            )
            self.conn.commit()

    def insert_book(self, ts: int, bids: list, asks: list) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO book_snapshots (ts, bids_json, asks_json) VALUES (?,?,?)",
                (ts, json.dumps(bids), json.dumps(asks)),
            )
            self.conn.commit()

    # --- reads ---
    def latest_candle(self, interval: str):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM candles WHERE interval=? ORDER BY open_ts DESC LIMIT 1",
                (interval,),
            ).fetchone()
        if r is None:
            return None
        return dict(r)

    def candle_open_timestamps(self, interval: str) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT open_ts FROM candles WHERE interval=? ORDER BY open_ts", (interval,)
            ).fetchall()
        return [row["open_ts"] for row in rows]

    def latest_ctx(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM market_ctx ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return dict(r) if r else None

    def recent_large_trades(self, limit: int = 20) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM trades WHERE is_large=1 ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_book(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM book_snapshots ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return dict(r) if r else None

    def recent_candles(self, interval: str, limit: int = 200) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM candles WHERE interval=? ORDER BY open_ts DESC LIMIT ?",
                (interval, limit),
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def insert_narrative_item(self, item) -> bool:
        with self._lock:
            cur = self.conn.execute(
                """INSERT OR IGNORE INTO narrative_items
                   (hash, ts, source, reliability_weight, title, body, url)
                   VALUES (?,?,?,?,?,?,?)""",
                (item.hash, item.ts, item.source, item.reliability_weight,
                 item.title, item.body, item.url),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def recent_narrative_items(self, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM narrative_items WHERE ts >= ? ORDER BY ts DESC",
                (since_ts,),
            ).fetchall()
        return [dict(r) for r in rows]

    def save_conclusion(self, conclusion: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO narrative_conclusions (generated_at, json) VALUES (?,?)",
                (conclusion["generated_at"], json.dumps(conclusion)),
            )
            self.conn.commit()

    def latest_conclusion(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM narrative_conclusions ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None

    def ctx_history(self, limit: int = 2) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM market_ctx ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def count_large_trades_since(self, since_ts: int) -> int:
        with self._lock:
            r = self.conn.execute(
                "SELECT COUNT(*) AS c FROM trades WHERE is_large=1 AND ts >= ?",
                (since_ts,),
            ).fetchone()
        return r["c"]

    def insert_chart_read(self, read: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO chart_reads
                   (ts, timeframe, trend, current_price, image_path, status, json)
                   VALUES (?,?,?,?,?, 'read', ?)""",
                (read["ts"], read.get("timeframe"), read.get("trend"),
                 read.get("current_price"), read.get("image_path"),
                 json.dumps(read)),
            )
            self.conn.commit()

    def insert_pending_chart_read(self, ts: int, image_path: str | None) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO chart_reads
                   (ts, timeframe, trend, current_price, image_path, status, json)
                   VALUES (?, 'unknown', 'unknown', NULL, ?, 'pending', ?)""",
                (ts, image_path, json.dumps({"ts": ts, "image_path": image_path,
                                             "status": "pending"})),
            )
            self.conn.commit()

    def pending_chart_reads(self) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT ts, image_path FROM chart_reads WHERE status='pending' "
                "ORDER BY ts DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def finalize_chart_read(self, ts: int, read: dict) -> bool:
        with self._lock:
            cur = self.conn.execute(
                """UPDATE chart_reads SET timeframe=?, trend=?, current_price=?,
                   image_path=?, status='read', json=? WHERE ts=?""",
                (read.get("timeframe"), read.get("trend"), read.get("current_price"),
                 read.get("image_path"), json.dumps(read), ts),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def recent_chart_reads(self, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM chart_reads WHERE ts >= ? ORDER BY ts DESC",
                (since_ts,),
            ).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def latest_chart_read(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM chart_reads WHERE status='read' "
                "ORDER BY ts DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None

    def get_setting(self, key: str, default=None):
        with self._lock:
            r = self.conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r["value"] if r else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)",
                (key, str(value)))
            self.conn.commit()

    def get_settings(self) -> dict:
        with self._lock:
            rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def insert_trade_call(self, call: dict) -> None:
        status = "no_trade" if call.get("decision") == "no_trade" else \
            call.get("status", "open")
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO trade_calls (generated_at, decision, status, json) "
                "VALUES (?,?,?,?)",
                (call["generated_at"], call.get("decision"), status, json.dumps(call)))
            self.conn.commit()

    def open_trade_calls(self) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM trade_calls WHERE status='open' "
                "ORDER BY generated_at").fetchall()
        return [json.loads(r["json"]) for r in rows]

    def update_call_outcome(self, generated_at: int, outcome: dict) -> None:
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM trade_calls WHERE generated_at=?",
                (generated_at,)).fetchone()
            if not r:
                return
            call = json.loads(r["json"])
            call.update({"status": outcome["status"],
                         "exit_price": outcome.get("exit_price"),
                         "r_multiple": outcome.get("r_multiple"),
                         "ambiguous": outcome.get("ambiguous", False),
                         "resolved_at": int(__import__("time").time() * 1000)})
            self.conn.execute(
                "UPDATE trade_calls SET status=?, json=? WHERE generated_at=?",
                (outcome["status"], json.dumps(call), generated_at))
            self.conn.commit()

    def candles_since(self, interval: str, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM candles WHERE interval=? AND open_ts > ? ORDER BY open_ts",
                (interval, since_ts)).fetchall()
        return [dict(r) for r in rows]

    def latest_trade_call(self):
        with self._lock:
            r = self.conn.execute(
                "SELECT json FROM trade_calls ORDER BY generated_at DESC LIMIT 1"
            ).fetchone()
        return json.loads(r["json"]) if r else None

    def recent_trade_calls(self, since_ts: int) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT json FROM trade_calls WHERE generated_at >= ? "
                "ORDER BY generated_at DESC", (since_ts,)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def insert_regime(self, r: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO regimes (ts, timeframe, label, features_json) "
                "VALUES (?,?,?,?)",
                (r["ts"], r["timeframe"], r["label"], r.get("features_json", "{}")))
            self.conn.commit()

    def insert_pattern_event(self, e: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO pattern_events
                   (ts, pattern_name, source, direction, features_json, fwd_4h, fwd_12h, fwd_24h)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (e["ts"], e["pattern_name"], e.get("source"), e.get("direction"),
                 e.get("features_json", "{}"), e.get("fwd_4h"), e.get("fwd_12h"), e.get("fwd_24h")))
            self.conn.commit()

    def upsert_pattern_stat(self, p: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO pattern_stats
                   (pattern_name, source, n_train, n_test, win_rate_train, win_lo_test,
                    win_hi_test, avg_move_pct, avg_move_hrs, direction, stable,
                    threshold, horizon, p_value, bh_significant, holdout_lo, n_holdout)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["pattern_name"], p.get("source"), p.get("n_train"), p.get("n_test"),
                 p.get("win_rate_train"), p.get("win_lo_test"), p.get("win_hi_test"),
                 p.get("avg_move_pct"), p.get("avg_move_hrs"), p.get("direction"),
                 1 if p.get("stable") else 0, p.get("threshold"), p.get("horizon"),
                 p.get("p_value"), 1 if p.get("bh_significant") else 0,
                 p.get("holdout_lo"), p.get("n_holdout")))
            self.conn.commit()

    def stable_pattern_stats(self, min_conf: float) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM pattern_stats WHERE stable=1 AND win_lo_test >= ? "
                "ORDER BY win_lo_test DESC", (min_conf,)).fetchall()
        return [dict(r) for r in rows]

    def insert_discovered_pattern(self, d: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT OR REPLACE INTO discovered_patterns "
                "(name, centroid_json, dominant_features_json, created_at) VALUES (?,?,?,?)",
                (d["name"], d.get("centroid_json", "{}"),
                 d.get("dominant_features_json", "{}"), d.get("created_at", 0)))
            self.conn.commit()

    def all_pattern_stats(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM pattern_stats ORDER BY win_lo_test DESC").fetchall()
        return [dict(r) for r in rows]

    def insert_event(self, e: dict) -> None:
        import json as _json
        with self._lock:
            self.conn.execute(
                """INSERT INTO events
                   (date_ms, type, label, magnitude_pct, magnitude_usd,
                    source_url, notes, description, correlated_assets)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (e["date_ms"], e.get("type"), e.get("label"), e.get("magnitude_pct"),
                 e.get("magnitude_usd"), e.get("source_url"), e.get("notes", ""),
                 e.get("description"), _json.dumps(e.get("correlated_assets") or [])))
            self.conn.commit()

    def update_event(self, e: dict) -> None:
        """Refresh a catalog event in place (matched on date_ms+type)."""
        import json as _json
        with self._lock:
            self.conn.execute(
                """UPDATE events SET label=?, magnitude_pct=?, magnitude_usd=?,
                   source_url=?, notes=?, description=?, correlated_assets=?
                   WHERE date_ms=? AND type=?""",
                (e.get("label"), e.get("magnitude_pct"), e.get("magnitude_usd"),
                 e.get("source_url"), e.get("notes", ""), e.get("description"),
                 _json.dumps(e.get("correlated_assets") or []),
                 e["date_ms"], e.get("type")))
            self.conn.commit()

    def all_events(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM events ORDER BY date_ms").fetchall()
        return [dict(r) for r in rows]

    def events_of_type(self, type_: str) -> list:
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE type=? ORDER BY date_ms", (type_,)).fetchall()
        return [dict(r) for r in rows]

    def upcoming_events_raw(self, now_ms: int, horizon_days: int) -> list:
        hi = now_ms + horizon_days * 86400_000
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM events WHERE date_ms > ? ORDER BY date_ms",
                (now_ms,)).fetchall()
        return [dict(r) for r in rows]

    def event_exists(self, date_ms: int, type_: str) -> bool:
        with self._lock:
            r = self.conn.execute(
                "SELECT 1 FROM events WHERE date_ms=? AND type=? LIMIT 1",
                (date_ms, type_)).fetchone()
        return r is not None

    def upsert_event_study(self, st: dict) -> None:
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO event_studies
                   (type, n, median_pre, median_post, median_trough, median_peak,
                    spread_json, confidence_label, computed_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (st["type"], st["n"], st.get("median_pre"), st.get("median_post"),
                 st.get("median_trough"), st.get("median_peak"),
                 st.get("spread_json", "{}"), st.get("confidence_label"),
                 st.get("computed_at", 0)))
            self.conn.commit()

    def event_study(self, type_: str):
        with self._lock:
            r = self.conn.execute(
                "SELECT * FROM event_studies WHERE type=?", (type_,)).fetchone()
        return dict(r) if r else None

    def all_event_studies(self) -> list:
        with self._lock:
            rows = self.conn.execute("SELECT * FROM event_studies").fetchall()
        return [dict(r) for r in rows]
