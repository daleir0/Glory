# Glory AI Site Revamp — Design Spec
**Date:** 2026-05-22  
**Status:** Approved

## Overview
Full visual and feature revamp of `glory-rooms` (Vite + React + TypeScript + Tailwind). Replace Claude-era dark terminal green aesthetic with a solar Glory theme. Rebuild navigation from sidebar tabs to a professional top navbar. Add pixel art character system, expanded dashboard, and united prompt pipeline.

## Theme

| Token | Value | Role |
|---|---|---|
| bg-base | `#0A0700` | Page background |
| gold | `#FFD700` | Primary accent |
| solar-white | `#FFFEF0` | Text, highlights |
| amber | `#FF9500` | Secondary glow |
| deep-gold | `#C8860A` | Borders, muted elements |
| void | `#1A1200` | Cards, panels |

Fonts: **Rajdhani** (headings/display) + **Share Tech Mono** (data/code, kept from current).  
Tailwind config updated with new color tokens replacing `ink-*` and `accent-500`.

## Navigation
Replace sidebar with a sticky top navbar:
```
[ ☀ GLORY ]   Home  Dashboard  Rooms  Agents  Scout  Pipeline     [ PROXY:OK · 3 MDL · 00:14:22 ]
```
- Active item: solar gold underline glow
- Status strip (proxy, model count, uptime) stays right-aligned
- Fully responsive

## Characters — Pixel Art Sprite System

32×48px CSS sprite animations. Characters render in a fixed overlay layer (z-index above content, pointer-events: none). Autonomous behavior driven by a `CharacterEngine` class.

| Model | Name | Sprite Style | Colors |
|---|---|---|---|
| Claude | Sol | Armored sun-knight, geometric radiant crown | Gold + white |
| Gemma | Gem | Crystal fairy, prismatic wings, gem-core | Teal + prismatic |
| Qwen | Sage | Robed owl scholar, staff + floating scrolls | Violet + amber |
| Hermes | Hermes | Winged messenger, caduceus, winged sandals | Silver + white |
| Kimi | Luna | Crescent moon navigator, star-map cape | Pale blue + silver |

### Autonomous Behavior
- Every 30–90s (random): a character walks across the viewport bottom
- When a prompt is routed to a model: that model's character runs to center, shows working animation
- Characters occasionally "meet" and show a small debate/chat bubble
- All animations: pure CSS keyframes, no canvas

## Dashboard (Expanded)
Rebuild `Dashboard.tsx` with a responsive grid of panels:

1. **Context Window** — live token meter (bar fills like fuel gauge), reads from proxy `/v1/context` or estimated
2. **Obsidian** — file watch on `E:\Glory\Glory's Intellect` → shows 5 most recently modified notes with title + excerpt
3. **Cron Jobs** — live list from proxy `/v1/crons`, with start/stop toggle
4. **Daily List** — editable textarea persisted to localStorage per day (keyed by YYYY-MM-DD)
5. **Research Feed** — 24h autoresearch stream, reads from `E:\Glory\autoresearch` output logs
6. **Portfolio** — manual tracker: enter projected revenue streams, auto-totals

## Rooms (Unchanged Structure, Restyled)
- GLORY, MODELS, AGENTS, Scout, Solo, Pipeline, Room, Debate all kept
- Restyled to match new theme

## United Prompt Pipeline
- Persistent floating input bar at bottom of every page (like a command palette)
- Clicking **GLORY** fans out to all available models simultaneously
- Responses shown in a 2-column card grid, color-coded by character color
- Individual model buttons also available for direct routing

## Scout / Web Scrape
`SiteInspector.tsx` kept as-is, exposed via **Scout** nav item.

## Implementation Approach
Parallel agent swarm:
1. **Theme Agent** — `App.tsx`, `index.css`, `tailwind.config.js` (new color tokens, top navbar)
2. **Character Agent** — `CharacterLayer.tsx` + `CharacterEngine.ts` + CSS sprites
3. **Dashboard Agent** — `Dashboard.tsx` full rebuild
4. **Pipeline Agent** — `UnifiedPipeline.tsx` floating input bar + fan-out logic
