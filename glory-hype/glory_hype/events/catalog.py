"""Curated HYPE catalyst catalog. Hand-verified; data decides nothing here — these are
facts we maintain. Dates are UTC. Magnitudes are best-known and flagged for verification."""

from datetime import datetime, timezone

# HYPE team vesting unlocks land on the 6th of each month (first Jan 6 2026).
# ETF/approval catalysts from project research. magnitude_pct = % of supply where known.
SEED_EVENTS = [
    {"date": "2026-01-06", "type": "unlock", "label": "Team vesting unlock (Jan)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th",
     "description": "Scheduled TGE vesting — monthly team allocation begins unlocking. Insiders gain liquid access to sell.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-02-06", "type": "unlock", "label": "Team vesting unlock (Feb)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th",
     "description": "Scheduled TGE vesting — monthly team allocation begins unlocking. Insiders gain liquid access to sell.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-03-06", "type": "unlock", "label": "Team vesting unlock (Mar)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th",
     "description": "Scheduled TGE vesting — monthly team allocation begins unlocking. Insiders gain liquid access to sell.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-04-06", "type": "unlock", "label": "Team vesting unlock (Apr)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th",
     "description": "Scheduled TGE vesting — monthly team allocation begins unlocking. Insiders gain liquid access to sell.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-05-06", "type": "unlock", "label": "Team vesting unlock (May)",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events", "notes": "monthly 6th",
     "description": "Scheduled TGE vesting — monthly team allocation begins unlocking. Insiders gain liquid access to sell.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-06-06", "type": "unlock", "label": "Team vesting unlock (Jun) — UPCOMING",
     "magnitude_pct": 2.54, "magnitude_usd": 6.84e8,
     "source_url": "https://tokenomist.ai/hyperliquid/unlock-events",
     "notes": "~9.92M HYPE; verify magnitude on the day",
     "description": "Scheduled TGE vesting — 684M USD team allocation begins unlocking. Insiders gain liquid access to sell. Largest monthly unlock so far.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
    {"date": "2026-05-18", "type": "listing", "label": "SpaceX pre-IPO perp listing",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "drove +7% vs down market",
     "description": "Hyperliquid listed a SpaceX pre-IPO perpetual — a novel instrument drawing new attention and volume to the platform.",
     "correlated_assets": []},
    {"date": "2026-05-26", "type": "etf", "label": "CFTC regulated-perp approval",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "drove ATH push",
     "description": "CFTC approval for regulated perpetual futures — legitimizes Hyperliquid's model for institutional participants and removes regulatory overhang.",
     "correlated_assets": ["NEAR", "ICP"]},
    {"date": "2026-06-03", "type": "etf", "label": "Grayscale HYPG ETF on Nasdaq",
     "magnitude_pct": None, "magnitude_usd": None,
     "source_url": "", "notes": "institutional on-ramp; drove the Jun 3 rally",
     "description": "Grayscale HYPG ETF listed on Nasdaq — institutional on-ramp enabling TradFi funds to gain HYPE exposure without self-custody.",
     "correlated_assets": ["NEAR", "ICP", "VVV"]},
]


def _to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def seed_catalog(store) -> int:
    """Insert SEED_EVENTS; refresh enriched fields on events already present
    (dedup by date+type). Returns count of newly inserted events."""
    added = 0
    for e in SEED_EVENTS:
        ms = _to_ms(e["date"])
        row = {"date_ms": ms, "type": e["type"], "label": e["label"],
               "magnitude_pct": e["magnitude_pct"],
               "magnitude_usd": e["magnitude_usd"],
               "source_url": e["source_url"], "notes": e["notes"],
               "description": e.get("description"),
               "correlated_assets": e.get("correlated_assets")}
        if store.event_exists(ms, e["type"]):
            store.update_event(row)
            continue
        store.insert_event(row)
        added += 1
    return added
