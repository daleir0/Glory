# Glory OS: Agent Environment & Web Researcher

**Date:** 2026-05-15  
**Status:** Approved  
**Scope:** Two independent features added to glory-rooms UI + proxy

---

## Feature 1: ASCII Agent Environment

### Overview

A new `AGENTS` sidebar mode that renders a live terminal-style scene showing all registered AI agents as ASCII characters at named workstations. The environment animates based on real session activity.

### Architecture

**Component:** `glory-rooms/ui/src/modes/AgentEnvironment.tsx`

- Polls `GET /v1/sessions` every 2 seconds for active sessions (updated within 30s)
- Polls `GET /v1/models` on mount for agent roster
- No new proxy endpoints required

**Sidebar:** New entry `{ key: 'agents', label: 'AGENTS', desc: 'Live agent workspace environment' }` added to the `MODES` array in `App.tsx`

### Layout

80-character wide monospace scene rendered as styled DOM (Share Tech Mono, no Canvas API):

```
╔══════════════════════════════════════════════════════════════════════════════╗
║  GLORY AGENT WORKSPACE          2 active  ·  1 session live                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────┐    ┌─────────────────────┐                         ║
║  │ @kimi               │    │ @gemma              │                         ║
║  │ ████████░░ 80%      │    │ ░░░░░░░░░░ idle     │                         ║
║  │ ▶ responding...     │    │ ■ standby           │                         ║
║  └─────────────────────┘    └─────────────────────┘                         ║
║               │ → → → → → → → ↑                                             ║
║               └── pipeline ───┘                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Agent States

| State | Indicator | Trigger |
|---|---|---|
| `idle` | `■ standby` + dim border | No recent session activity |
| `thinking` | `⠋ thinking...` (spinner) | Session updated < 5s ago |
| `responding` | `▶ responding...` + progress bar | Session updated < 30s ago |
| `done` | `✓ complete` | Session closed |

### Data Flow

Active sessions are detected by `updated_at` recency. If a session involves multiple models (Room/Pipeline), connecting arrows (`→ → →`) are drawn between those agents' stations. Session mode badge shown on the connection line.

---

## Feature 2: Web Researcher

### Overview

A new Dashboard section with a URL input that scrapes a target site and saves structured research notes to both the glory-rooms SQLite DB and the Obsidian vault (`Glory's Intellect/05 - Research/`).

### Architecture

**Backend:** `POST /v1/research` in `glory-rooms/proxy/lm-proxy.py`
- Python stdlib only: `urllib`, `html.parser`, `re`, `json`
- No external dependencies

**Frontend:** New section in `Dashboard.tsx`

**Obsidian target:** `D:\Glory\Glory's Intellect\05 - Research\YYYY-MM-DD-{domain}.md`

**DB:** New `research_log` SQLite table for history

### Proxy Endpoint

**Request:**
```json
POST /v1/research
{ "url": "https://example.com" }
```

**Extraction:**
- HTTP response: status code, headers (Server, X-Powered-By, Content-Type, Cache-Control)
- HTML parsing: title, meta description, canonical URL, Open Graph tags
- Tech detection: script/link href patterns → React, Next.js, Vue, Nuxt, Angular, Webpack, Vite, GA4, Segment, Mixpanel, nginx, Apache, Cloudflare
- Links: all `<a href>` → split internal vs. external (deduplicated, max 100)
- Assets: all `<script src>` and `<link href>` with byte sizes where available
- API patterns: regex scan over all href/src paths for `/api/`, `/graphql`, `/v1/`, `/v2/`, `/rest/`, `/rpc/`

**Response:**
```json
{
  "url": "https://example.com",
  "domain": "example.com",
  "status": 200,
  "server": "nginx/1.24",
  "title": "Example Domain",
  "description": "...",
  "tech_stack": ["React", "Webpack", "GA4"],
  "links": { "internal": [...], "external": [...] },
  "assets": [{ "url": "...", "type": "script" }],
  "api_patterns": ["/api/v2/users", "/graphql"],
  "obsidian_path": "D:\\Glory\\Glory's Intellect\\05 - Research\\2026-05-15-example-com.md",
  "saved": true
}
```

### Obsidian File Format

```markdown
---
url: https://example.com
domain: example.com
date: 2026-05-15
status: 200
server: nginx/1.24
tech_stack: [React, Webpack, GA4]
---

# Research: example.com

**Scraped:** 2026-05-15 13:00 UTC  
**Status:** 200 OK  
**Server:** nginx/1.24  
**Tech Stack:** React · Webpack · GA4

## API Endpoints
- /api/v2/users
- /graphql

## Assets (3)
- main.abc123.js (script)
- vendor.def456.js (script)
- styles.css (stylesheet)

## Internal Links (12)
- /about
- /pricing
...

## External Links (5)
- https://cdn.example.com
...
```

### SQLite Table

```sql
CREATE TABLE IF NOT EXISTS research_log (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  domain TEXT NOT NULL,
  status INTEGER,
  tech_stack TEXT,
  api_patterns TEXT,
  obsidian_path TEXT,
  scraped_at TEXT DEFAULT (datetime('now'))
);
```

### Dashboard UI

- URL input + "Scrape" button
- Loading indicator while fetching
- Results: Status badge, Tech stack pills, API endpoints list, Asset count, Link counts
- "Saved to Obsidian" path shown on success
- Recent scrapes history (last 10 from `research_log`)

---

## Implementation Order

1. `AgentEnvironment.tsx` — new component
2. `App.tsx` — add AGENTS to MODES
3. `lm-proxy.py` — add `research_log` table + `POST /v1/research` handler
4. `api.ts` — add `api.research()` call
5. `Dashboard.tsx` — add Research section
