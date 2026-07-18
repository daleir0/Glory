"""On-demand synthesis: recent items + market ctx -> Claude (via proxy) -> Conclusion."""

import time

from glory_hype import config
from glory_hype.narrative.conclusion import parse_conclusion, unavailable
from glory_hype.narrative.proxy_client import ProxyClient, ProxyError

DEFAULT_WINDOW_MS = 7 * 24 * 60 * 60 * 1000  # 7d
MAX_PROMPT_ITEMS = 60  # cap prompt size; rank by reliability then recency

_SYSTEM = (
    "You are Glory's narrative analyst for the Hyperliquid HYPE perpetual. "
    "You are given narrative items from multiple sources, each tagged with a "
    "reliability weight (1.0 = guaranteed on-chain fact, lower = noisier). "
    "Weight high-reliability sources more heavily and do NOT let a volume of "
    "low-reliability noise override hard facts. Read the narrative against the "
    "live market context. Be honest: if the move looks extended or signals "
    "conflict, say so in caution_flags. "
    "OUTPUT RULES: No thinking, no preamble, no explanation. "
    "Respond with ONLY a valid JSON object on a single line: "
    "{\"bias\": \"bullish|bearish|neutral\", "
    "\"confidence\": 0.0-1.0, \"key_drivers\": [..], \"caution_flags\": [..], "
    "\"source_breakdown\": {source: count}}."
)


def build_prompt(items: list, ctx: dict | None) -> list:
    lines = ["LIVE MARKET CONTEXT:"]
    if ctx:
        lines.append(
            f"  mark={ctx.get('mark_px')} funding={ctx.get('funding')} "
            f"open_interest={ctx.get('open_interest')} "
            f"prev_day_px={ctx.get('prev_day_px')} "
            f"24h_notional_vol={ctx.get('day_ntl_vlm')}")
    else:
        lines.append("  (no market context available)")
    lines.append("\nNARRATIVE ITEMS (with reliability weights):")
    ranked = sorted(items, key=lambda it: (it["reliability_weight"], it["ts"]),
                    reverse=True)[:MAX_PROMPT_ITEMS]
    for it in ranked:
        lines.append(
            f"  [{it['source']} reliability={it['reliability_weight']:.1f}] "
            f"{it['title']} :: {it['body'][:200]}")
    lines.append("\nReturn ONLY the JSON object described.")
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": "\n".join(lines)}]


class Synthesizer:
    def __init__(self, store, proxy=None, window_ms: int = DEFAULT_WINDOW_MS):
        self.store = store
        self._owns_proxy = proxy is None
        self.proxy = proxy or ProxyClient(
            base_url=config.LM_STUDIO_URL,
            model=config.LM_STUDIO_MODEL
        )
        self.window_ms = window_ms

    def close(self):
        if self._owns_proxy:
            self.proxy.close()

    def synthesize(self):
        now = int(time.time() * 1000)
        items = self.store.recent_narrative_items(since_ts=now - self.window_ms)
        based_on = [it["hash"] for it in items]
        ctx = self.store.latest_ctx()
        msgs = build_prompt(items, ctx)
        try:
            raw = self.proxy.chat(msgs, max_tokens=800)
        except ProxyError:
            c = unavailable(generated_at=now)
            c.based_on = based_on
            self.store.save_conclusion(c.to_dict())
            return c
        c = parse_conclusion(raw, based_on=based_on, generated_at=now)
        self.store.save_conclusion(c.to_dict())
        return c
