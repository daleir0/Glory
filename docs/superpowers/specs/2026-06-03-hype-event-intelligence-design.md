---
title: Glory HYPE — Event-Anchored Intelligence (v9.2)
date: 2026-06-03
status: draft (awaiting user review)
project: Glory Trading Intelligence
phase: v9.2 (event-study layer; complements v9/v9.1 statistical patterns)
builds_on: 2026-06-03-hype-pattern-deepening-design.md
---

# Glory HYPE — Event-Anchored Intelligence (v9.2)

## Purpose

Catalog HYPE's fundamental catalysts (token unlocks, ETF launches, listings), study how
price / funding / OI behaved in the window around each past one (the **playbook**), and
surface a **forward alert** for upcoming catalysts — the **June 6 unlock first** — with
"here's what history suggests." This is the right tool for fundamental events that don't
need 18 months of statistical instances; it needs the curated history of a handful of
high-impact events.

**Honesty mandate (non-negotiable):** with a small event catalog this is an *event study*
— descriptive, not inferential. Every output states the **N** it rests on, labels small-N
sets "directional only," and never attaches a fabricated confidence %. It informs the
agent's judgment; it does NOT statistically gate trades (that remains v9/v9.1's job).

## Decisions locked (from brainstorming)

- **Manual curated catalog** — hand-verified event dates/types/magnitudes; we maintain it.
- **Output = playbook + forward alert** — composite window study per event-type, plus a
  countdown + "what history suggests" for upcoming events.
- **Window default −7d/+7d** (configurable) — wide enough to capture anticipation/run-up.
- Event study is **descriptive**; no significance testing (wrong tool for small N).

## 1. Curated event catalog

`events` table: `id, date_ms, type, label, magnitude_pct, magnitude_usd, source_url,
notes`. `type` ∈ {`unlock`, `etf`, `listing`, `upgrade`, `other`}. Seeded by research with
HYPE's real catalysts since launch (Nov 2024) — the periodic token unlocks, the Bitwise /
Grayscale (HYPG) ETF launches, the CFTC regulated-perp approval, major listings. **The
June 6 unlock is seeded as a FUTURE event** (magnitude ~9.92M HYPE / ~2.54% supply /
~$684M — flagged verify-on-day). CLI `events add` appends new catalysts as announced.

## 2. Event-study analyzer (`eventstudy.py`, pure)

`study_event(event, candles, ctx_rows, window_days) -> dict`:
- Slice our 1h candle + ctx data from `event.date − window` to `event.date + window`.
- Normalize price to **100 at the event time** → relative path.
- Track funding and OI trajectories across the window.
- Return `pre_pct` (price change event-start → event), `post_pct` (event → window-end),
  `trough_pct` / `peak_pct` (max drawdown / runup in the window), funding/OI deltas, and
  the normalized path samples.

`composite(study_list) -> dict`: across all studies of one event-type, the **median**
pre/post/trough/peak (median, not mean — robust to a single outlier on small N), the
**min/max spread**, and the **N**. If N < 3 → `confidence_label="insufficient history —
directional only"`, else `"small-sample composite (N=k)"`.

## 3. Forward alert (`upcoming.py`)

`upcoming_events(store, now_ms, horizon_days) -> list`: catalog events with
`date_ms > now`, within `horizon_days`, each annotated with `days_until` and the matching
event-type **composite** ("what history suggests"). A proximity flag fires for events
≤ 3 days out (configurable): e.g. "⚠️ unlock in 3d — past unlocks (N=k) ran {pre}% into
the date, {post}% after."

## 4. v4 + dashboard integration

- **v4 `record_call`** gains `inputs["event_context"]`: nearest upcoming catalyst within
  N days + its historical composite. **A major event (unlock/etf) within 48h adds a
  caution flag** to the agent's consideration (don't hold into a known supply shock — the
  June 6 risk made concrete). The agent weighs it; it's a caution input, not a hard gate.
- **Dashboard Events panel** (in the existing **Intel** tab): upcoming catalysts with
  countdown + composite, and the per-type playbook table.

## Architecture / files

```
glory-hype/glory_hype/events/
  __init__.py
  catalog.py      # seed list + add/list helpers over the events table
  eventstudy.py   # pure: study_event, composite
  upcoming.py     # forward alert: upcoming_events + proximity flags
glory-hype/glory_hype/
  db.py           # MODIFY: events + event_studies tables + methods
  decision/engine.py # MODIFY: add event_context to inputs + 48h caution
  server.py       # MODIFY: /api/events (upcoming + playbook)
  static/index.html  # MODIFY: Events panel in the Intel tab
  __main__.py     # MODIFY: `events` subcommand (analyze | add | upcoming)
  config.py       # MODIFY: EVENT_WINDOW_DAYS, EVENT_ALERT_DAYS, EVENT_CAUTION_HRS
```

No new external dependency.

### Storage
- `events(id INTEGER PK, date_ms, type, label, magnitude_pct, magnitude_usd, source_url, notes)`
- `event_studies(type TEXT PRIMARY KEY, n INTEGER, median_pre REAL, median_post REAL,
  median_trough REAL, median_peak REAL, spread_json TEXT, confidence_label TEXT,
  computed_at INTEGER)`
- Store methods: `insert_event`, `all_events`, `upcoming_events_raw(now, horizon)`,
  `events_of_type(type)`, `upsert_event_study`, `event_study(type)`, `all_event_studies`.

## Data flow

```
research -> events table (curated, incl. future Jun 6 unlock)
        │  events analyze
        ▼
  per past event: study_event (our candles/ctx, ±7d, normalized path)
        │  composite per type (median + spread + N + honesty label)
        ▼
  event_studies (cached playbook)
        │
  upcoming_events (future catalog rows + matching composite + proximity flag)
        ├─► /api/events + Intel-tab Events panel
        └─► v4 record_call: inputs.event_context + 48h caution flag
```

## Error handling

- Event date outside our candle coverage (e.g. older than our 1h history) → that event is
  skipped in the study, logged; composite uses only studiable events (N reflects this).
- No events of a type → no composite; the playbook omits it cleanly.
- Future event with no historical composite for its type → alert still shows the countdown
  with "no comparable history" instead of a fabricated expectation.
- Sparse ctx in a window → funding/OI deltas default to None; price path still computed.

## Verification / success criteria

- Seeding + `all_events` round-trips the curated catalog incl. the future June 6 unlock.
- `study_event` on a crafted window returns correct pre/post/trough/peak and a path
  normalized to 100 at the event (unit-tested).
- `composite` returns median + spread + N and the right honesty label at N<3 vs N≥3.
- `upcoming_events` surfaces the June 6 unlock with days_until and a proximity flag, and
  attaches the unlock composite (or "insufficient history" if <3 past unlocks studiable).
- v4 `record_call` carries `event_context`; a seeded event 24h out adds the caution flag.
- `/api/events` returns upcoming + playbook; Intel-tab panel renders them.
- Real run: `events analyze` over the seeded catalog prints the unlock/ETF playbook from
  our actual data — honestly labeled by N.

## Testing

- **Offline-unit:** `study_event` (pre/post/trough/peak + normalization), `composite`
  (median/spread/N + label thresholds), `upcoming_events` (countdown + proximity flag +
  composite attach), catalog seed/add, Store event methods, v4 event_context + 48h caution.
- **Integration (seeded DB):** insert 3 synthetic past unlocks with known paths + 1 future
  unlock → `events analyze` builds a composite → `upcoming` attaches it with a flag.
- **Real-data smoke (`live`, opt-in):** seed the real catalog, run `events analyze` on
  hype.db, print the playbook (honest N labels).

## Out of scope

- Statistical significance testing (wrong tool for small N — that's v9/v9.1).
- Auto-scraping unlock/event data (manual curation by decision).
- Cross-asset / macro events.
- Trading automatically on event signals (informs; execution stays v6-v8 track).

## Why this is the honest, timely path

The June 6 unlock is ~3 days out — a known, dated, fundamental supply shock. No amount of
price-pattern statistics predicts it; the catalog does. v9.2 turns "we vaguely know
unlocks are bearish" into "past unlocks (N=k) ran X% into the date and Y% after, and the
next one is in 3 days" — a concrete, honestly-bounded heads-up in front of you before it
hits, plus a v4 caution so we don't hold into it. Small sample, stated plainly; still far
better than flying blind into a catalyst we can see coming.
