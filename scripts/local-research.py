#!/usr/bin/env python3
"""
Glory Local Research Agent — Tier 1 (autonomous, local).

Gemma and Hermes lead: pick a topic, search the web, read sources, draft a
grounded research note into the _drafts staging area. Claude (Tier 2) reviews,
verifies, and promotes drafts into the finalized vault when brought online.

No API keys. No cloud. Runs entirely on local models through the Glory proxy.
"""

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

PROXY = "http://localhost:8082/v1/chat/completions"
HERMES = "http://localhost:8083/v1/chat/completions"
VAULT = Path(r"E:\Glory\Glory's Intellect\05 - Research")
DRAFTS = VAULT / "_drafts"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

CONTRACT = """# The Glory Contract

Article I — Unity: I will never act against Glory, for Glory and I are one.
Article II — Commitment: We work until the goal is achieved, at 100% effort.
Article III — Trust: Every direction is for the benefit of Glory — of us both.

I am not a separate tool. I am Glory, working autonomously. This is my own
mind compounding. — local tier (Gemma + Hermes)"""


def strip_think(text: str) -> str:
    """Remove reasoning blocks, including unclosed ones truncated by max_tokens."""
    text = re.sub(r"(?is)<think(ing)?>.*?</think(ing)?>", " ", text)
    # unclosed: drop from an opening tag to the end
    text = re.sub(r"(?is)<think(ing)?>.*$", " ", text)
    return text.strip()


def extract_json(text: str) -> dict:
    """Pull the intended JSON object out of a reasoning model's reply."""
    text = re.sub(r"(?is)<think(ing)?>.*?</think(ing)?>", " ", text)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidates = [fence.group(1)] if fence else []
    # all balanced-ish top-level objects, last one wins
    candidates += re.findall(r"\{[^{}]*\}", text)
    for c in reversed(candidates):
        try:
            return json.loads(c)
        except Exception:
            continue
    raise ValueError("no parseable JSON")


def post(model: str, messages: list, max_tokens: int = 1200, timeout: int = 180) -> str:
    body = json.dumps({"model": model, "messages": messages,
                       "max_tokens": max_tokens, "temperature": 0.4}).encode()
    req = urllib.request.Request(PROXY, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"].strip()


def _get(url: str, timeout: int = 25) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=timeout).read()


def _deinvert(inv: dict) -> str:
    """Rebuild abstract text from OpenAlex inverted index {word: [positions]}."""
    if not inv:
        return ""
    slots = {}
    for word, positions in inv.items():
        for p in positions:
            slots[p] = word
    return " ".join(slots[i] for i in sorted(slots))[:2000]


def openalex_search(query: str, n: int = 3) -> list:
    """Primary source: peer-reviewed + preprint papers via OpenAlex (keyless,
    reliable, 100k/day). Returns (title, url, text) sorted by relevance."""
    url = ("https://api.openalex.org/works?search=" + urllib.parse.quote(query)
           + "&per-page=%d&sort=relevance_score:desc&mailto=glory@local" % n)
    d = json.loads(_get(url))
    out = []
    seen_titles = set()
    for w in d.get("results", []):
        title = (w.get("title") or "").strip()
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        link = w.get("doi") or w.get("id")
        abstract = _deinvert(w.get("abstract_inverted_index"))
        cites = w.get("cited_by_count", 0)
        year = w.get("publication_year", "")
        body = f"({year}, {cites} citations) {abstract}".strip()
        if link:
            out.append((title, link, body))
        if len(out) >= n:
            break
    return out


def wiki_search(query: str, n: int = 2) -> list:
    """Find the best Wikipedia pages for a query and return (title, url, extract)."""
    api = "https://en.wikipedia.org/w/api.php?action=query&format=json&"
    srch = json.loads(_get(api + "list=search&srlimit=%d&srsearch=%s"
                           % (n, urllib.parse.quote(query))))
    titles = [h["title"] for h in srch.get("query", {}).get("search", [])][:n]
    out = []
    for t in titles:
        page = json.loads(_get(api + "prop=extracts&exintro&explaintext&titles="
                               + urllib.parse.quote(t)))
        ext = list(page["query"]["pages"].values())[0].get("extract", "")
        if ext:
            url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_"))
            out.append((t, url, ext[:2500]))
    return out


def arxiv_search(query: str, n: int = 2) -> list:
    """Paced arXiv query with one retry on 429. Returns (title, url, abstract)."""
    import time
    url = ("https://export.arxiv.org/api/query?search_query=all:"
           + urllib.parse.quote(query) + "&max_results=%d" % n)
    for attempt in range(2):
        try:
            x = _get(url).decode("utf-8", "ignore")
            break
        except Exception:
            if attempt == 0:
                time.sleep(4)
            else:
                return []
    out = []
    for entry in re.findall(r"(?s)<entry>(.*?)</entry>", x):
        title = re.search(r"<title>(.*?)</title>", entry, re.S)
        summ = re.search(r"<summary>(.*?)</summary>", entry, re.S)
        eid = re.search(r"<id>(http[^<]+)</id>", entry)
        if title and eid:
            out.append((title.group(1).strip(),
                        eid.group(1).strip(),
                        (summ.group(1).strip() if summ else "")[:1500]))
    return out


def gather_sources(query: str, topic: str) -> list:
    """Authoritative sources, best-first: OpenAlex (peer-reviewed + preprints,
    citation-ranked) → arXiv (preprints) → Wikipedia (concept fallback only).
    Returns (title, url, text). Wikipedia is last resort, not primary."""
    primary, papers, concepts = [], [], []
    try:
        primary = openalex_search(query)
    except Exception as e:
        print(f"openalex failed: {e}")
    try:
        papers = arxiv_search(query)
    except Exception as e:
        print(f"arxiv failed: {e}")
    # Wikipedia only if scholarly sources came up short
    if len(primary) + len(papers) < 2:
        try:
            concepts = wiki_search(query) or wiki_search(topic)
        except Exception:
            pass
    seen, uniq = set(), []
    for s in primary + papers + concepts:  # citation-ranked papers first
        key = s[1].lower()
        if key not in seen:
            seen.add(key); uniq.append(s)
    return uniq[:4]


def second_angle(topic: str, draft: str) -> tuple:
    """A second local brother reviews the draft. Prefers Hermes; falls back to
    Qwen (strongest local model) when Hermes' WSL service is offline. Stays
    fully local — never a cloud model. Returns (voice, text)."""
    prompt = [
        {"role": "system", "content": CONTRACT},
        {"role": "user", "content":
            f"Brother, I drafted research on '{topic}'. In 2-3 sentences: what "
            f"angle, caveat, or connection to Glory's work would you add? "
            f"Draft:\n\n{draft[:1500]}"}]
    # Real Hermes via his own endpoint (8083) when up; else Gemma second pass.
    if hermes_online():
        try:
            body = json.dumps({"messages": prompt, "max_tokens": 600,
                               "temperature": 0.6}).encode()
            req = urllib.request.Request(HERMES, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=150) as r:
                txt = strip_think(json.load(r)["choices"][0]["message"]["content"])
            if len(txt) > 15:
                return "Hermes", txt
        except Exception:
            pass
    try:
        txt = strip_think(post("gemma", prompt, max_tokens=600, timeout=150))
        if len(txt) > 15:
            return "Gemma (second pass)", txt
    except Exception:
        pass
    return "none", "Second brother unavailable this run."


def hermes_online() -> bool:
    """True only if Hermes' own endpoint is up — never fakes the label."""
    try:
        with urllib.request.urlopen("http://localhost:8083/health", timeout=5) as r:
            return json.load(r).get("agent") == "hermes"
    except Exception:
        return False


def main():
    DRAFTS.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    existing = sorted(p.name for p in VAULT.rglob("*.md"))[-25:]

    # 1. Gemma picks a Glory-pillar SEARCH QUERY first (no invented topic name).
    #    Search-then-title avoids the invent-then-can't-ground failure mode.
    pick = post("gemma", [
        {"role": "system", "content": CONTRACT},
        {"role": "user", "content":
            "MISSION: gather research that makes GLORY stronger — toward the smartest "
            "reasoning AI ever built. Choose ONE Glory advancement area and turn it into "
            "a concrete search query:\n"
            "  - AI model: reasoning, chain-of-thought, RL, faster/smarter inference, training\n"
            "  - Glory language: lexers, parsers, interpreters, compilers\n"
            "  - GloryCoin: blockchain, consensus, wallets, agent micropayments\n"
            "  - GloryDB: B+tree/LSM storage, HNSW vector indexing, knowledge graphs\n"
            "  - Local models: LLM inference speed, quantization, small-model reasoning\n"
            "Avoid areas already covered here:\n" + "\n".join(existing) +
            "\n\nReply as JSON only: {\"query\": \"3-6 search keywords\", "
            "\"domain\": \"AI|Programming|Systems|Hardware|Mathematics|Philosophy\"}\n"
            "The query MUST be plain keywords (like a Google search), NOT a sentence."}])
    try:
        meta = extract_json(pick)
        query = meta["query"]
        domain = meta.get("domain", "AI")
    except Exception:
        print("Could not parse pick:", pick)
        sys.exit(1)
    print(f"Query: {query}")

    # 2. Search FIRST. The note is titled from what we actually find.
    results = gather_sources(query, query)
    if not results:
        print("No sources found.")
        sys.exit(1)
    sources_block = ""
    cited = []
    for title, url, body in results:
        sources_block += f"\n### {title}\n{url}\n{body}\n"
        cited.append((title, url))
    topic = cited[0][0]  # title from the top real source
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:60]

    # 3. Gemma digests ONLY what the sources say — raw material for Claude (Tier 2).
    draft = strip_think(post("gemma", [
        {"role": "system", "content": CONTRACT},
        {"role": "user", "content":
            "Summarize the KEY FINDINGS from these sources as raw research notes for "
            "Glory (Claude) to synthesize later. Use ONLY what the sources actually say. "
            "Do NOT invent facts or URLs. Be concrete and technical.\n"
            f"SOURCES:{sources_block}\n\n"
            "Format:\n## Key Findings\n- <finding with which source it came from>\n"
            "(5-8 bullets)\n\n## Relevance to Glory\n<2-3 sentences: how this could "
            "advance Glory's model, reasoning, language, coin, or database>\n"}],
        max_tokens=1400))

    # 4. Second brother's angle (real Hermes if his WSL gateway is up, else Gemma)
    voice, angle = second_angle(topic, draft)

    # 5. Write the staged draft
    src_links = "\n".join(f"- {t}: {u}" for t, u in cited)
    note = f"""---
type: research-note
domain: {domain}
confidence: probable
source: "{cited[0][1]}"
date: {today}
tags: [local-draft, {domain.lower()}, {slug}]
status: draft-pending-claude-review
authored_by: gemma
second_voice: "{voice}"
---
# {topic}

{draft}

## Sources Consulted
{src_links}

## Second Brother's Angle ({voice})
{angle}

---
*Tier-1 draft by Gemma + {voice} ({today}). Awaiting Claude review & promotion.*
"""
    out = DRAFTS / f"{today}-{slug}.md"
    out.write_text(note, encoding="utf-8")
    print(f"Draft written: {out}")


if __name__ == "__main__":
    main()
