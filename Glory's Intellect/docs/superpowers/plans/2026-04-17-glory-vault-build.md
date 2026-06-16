# Glory's Intellect Vault Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build out the full Glory's Intellect Obsidian vault — folder structure, templates, Atlas, Trading domain, Wiki, seed topic pages, and Obsidian configuration.

**Architecture:** Numbered top-level folders for domain separation, YAML frontmatter on every note for queryability, Atlas MOCs as navigation hubs, Command Inbox as the human-to-Glory trigger point.

**Tech Stack:** Obsidian Markdown, YAML frontmatter, Wikilinks (`[[]]`), Obsidian app.json config

---

## File Map

**Create:**
- `00 - Command Inbox/_README.md` — inbox usage instructions
- `01 - Sessions/2026-04-17.md` — today's session log
- `02 - Topics/Trading.md` — trading topic page
- `02 - Topics/Crypto.md` — crypto topic page
- `02 - Topics/Programming.md` — programming topic page
- `03 - Trading/Journal/_template.md` — trade journal template
- `03 - Trading/Strategies/_template.md` — strategy template
- `03 - Trading/Watchlists/Main.md` — active watchlist
- `03 - Trading/Analysis/_template.md` — analysis template
- `04 - Projects/_template.md` — project template
- `05 - Research/_template.md` — research template
- `06 - Ideas/_template.md` — idea template
- `07 - Atlas/HOME.md` — vault front door
- `07 - Atlas/INDEX.md` — full vault map
- `08 - Templates/command.md` — command inbox template
- `08 - Templates/session.md` — session log template
- `08 - Templates/topic.md` — topic page template
- `08 - Templates/trade.md` — trade journal template
- `08 - Templates/project.md` — project template
- `08 - Templates/research.md` — research template
- `08 - Templates/idea.md` — idea template
- `08 - Templates/wiki.md` — wiki page template
- `Wiki/Trading-Glossary.md` — trading terms reference
- `Wiki/Crypto-Glossary.md` — crypto terms reference
- `_Archive/.keep` — keeps archive folder visible

**Modify:**
- `.obsidian/app.json` — set startup file to `07 - Atlas/HOME.md`

---

## Task 1: Create Folder Skeleton

**Files:**
- Create: `_Archive/.keep`

- [ ] **Step 1: Create all required directories**

```bash
mkdir -p "D:\Glory\Glory's Intellect/00 - Command Inbox"
mkdir -p "D:\Glory\Glory's Intellect/01 - Sessions"
mkdir -p "D:\Glory\Glory's Intellect/02 - Topics"
mkdir -p "D:\Glory\Glory's Intellect/03 - Trading/Journal"
mkdir -p "D:\Glory\Glory's Intellect/03 - Trading/Strategies"
mkdir -p "D:\Glory\Glory's Intellect/03 - Trading/Watchlists"
mkdir -p "D:\Glory\Glory's Intellect/03 - Trading/Analysis"
mkdir -p "D:\Glory\Glory's Intellect/04 - Projects"
mkdir -p "D:\Glory\Glory's Intellect/05 - Research"
mkdir -p "D:\Glory\Glory's Intellect/06 - Ideas"
mkdir -p "D:\Glory\Glory's Intellect/07 - Atlas"
mkdir -p "D:\Glory\Glory's Intellect/08 - Templates"
mkdir -p "D:\Glory\Glory's Intellect/Wiki"
mkdir -p "D:\Glory\Glory's Intellect/_Archive"
```

- [ ] **Step 2: Verify all folders exist**

```bash
ls "D:\Glory\Glory's Intellect/"
```
Expected: All 10+ numbered folders plus Wiki, _Archive, raw-sources, docs visible.

- [ ] **Step 3: Create _Archive placeholder**

Write `_Archive/.keep` with empty content so the folder is visible in Obsidian.

---

## Task 2: Create All Templates

**Files:**
- Create: `08 - Templates/command.md`
- Create: `08 - Templates/session.md`
- Create: `08 - Templates/topic.md`
- Create: `08 - Templates/trade.md`
- Create: `08 - Templates/project.md`
- Create: `08 - Templates/research.md`
- Create: `08 - Templates/idea.md`
- Create: `08 - Templates/wiki.md`

- [ ] **Step 1: Write command.md template**

```markdown
---
type: command
created: {{date}}
status: pending
priority: normal
---
# Task: 

## Context

## Output Location
```

- [ ] **Step 2: Write session.md template**

```markdown
---
type: session
created: {{date}}
tags: []
topics-touched: []
---
# Session — {{date}}

## Commands Run

## Research Done

## Decisions Made

## Notes Updated
```

- [ ] **Step 3: Write topic.md template**

```markdown
---
type: topic
created: {{date}}
updated: {{date}}
status: seed
tags: []
---
# Topic: 

## Overview

## Key Concepts

## Resources

## Connected Topics

## Session History
```

- [ ] **Step 4: Write trade.md template**

```markdown
---
type: trade
date: {{date}}
asset: 
direction: 
entry: 
exit: 
result: 
pnl: 
tags: []
---
# Trade — [ASSET] {{date}}

## Setup
<!-- What pattern/signal triggered the trade? -->

## Execution
<!-- Entry, size, stop, target -->

## Outcome
<!-- What happened, final P&L -->

## Lesson
<!-- What to repeat or avoid next time -->
```

- [ ] **Step 5: Write project.md template**

```markdown
---
type: project
created: {{date}}
status: planning
goal: 
deadline: 
tags: []
---
# Project: 

## Goal

## Plan
- [ ] Step 1
- [ ] Step 2

## Progress

## Outcome
```

- [ ] **Step 6: Write research.md template**

```markdown
---
type: research
created: {{date}}
topic: 
sources: []
tags: []
---
# Research: 

## Summary

## Key Findings

## Sources

## Related Topics
```

- [ ] **Step 7: Write idea.md template**

```markdown
---
type: idea
created: {{date}}
status: raw
tags: []
---
# Idea: 

## The Idea

## Why It Matters

## Next Steps
```

- [ ] **Step 8: Write wiki.md template**

```markdown
---
type: wiki
created: {{date}}
updated: {{date}}
tags: []
---
# 

## Definition

## Key Points

## Examples

## Related
```

- [ ] **Step 9: Verify all 8 templates exist**

```bash
ls "D:\Glory\Glory's Intellect/08 - Templates/"
```
Expected: command.md, session.md, topic.md, trade.md, project.md, research.md, idea.md, wiki.md

---

## Task 3: Command Inbox README

**Files:**
- Create: `00 - Command Inbox/_README.md`

- [ ] **Step 1: Write _README.md**

```markdown
---
type: meta
---
# Command Inbox — How It Works

Drop a note here to give Glory a task.

## How to Create a Command

1. Create a new note in this folder
2. Name it anything descriptive (e.g., `Research Bitcoin ETFs.md`)
3. Use this structure:

---
type: command
created: YYYY-MM-DD
status: pending
priority: normal
---
# Task: [what you want done]

## Context
[any details, links, files Glory should know about]

## Output Location
[optional: where you want the output — defaults to appropriate folder]

---

## Priority Levels
- `high` — do this first
- `normal` — standard queue
- `low` — whenever

## Status Values
- `pending` — not yet started
- `in-progress` — Glory is working on it
- `done` — completed, safe to archive

## After Glory Completes
- Output will be in the appropriate folder
- This command note will be marked `status: done`
- Today's session log will reference it
```

- [ ] **Step 2: Verify file exists and is readable in Obsidian**

Open Obsidian, navigate to `00 - Command Inbox/_README.md`. Confirm it renders correctly.

---

## Task 4: Build the Atlas

**Files:**
- Create: `07 - Atlas/HOME.md`
- Create: `07 - Atlas/INDEX.md`

- [ ] **Step 1: Write HOME.md**

```markdown
---
type: atlas
created: 2026-04-17
---
# Glory's Intellect

> *"Your task will be whatever idea I present — and Glory will achieve it."*

---

## Quick Access
- [[00 - Command Inbox/_README|Command Inbox]] — Drop a task for Glory
- [[03 - Trading/Journal/_template|Trade Journal]] — Log a trade
- [[07 - Atlas/INDEX|Full Index]] — Map of everything

---

## Active Projects
*None yet — create one in [[04 - Projects]]*

---

## Recent Sessions
- [[01 - Sessions/2026-04-17|2026-04-17]] — Vault built

---

## Hot Topics
- [[02 - Topics/Trading|Trading]]
- [[02 - Topics/Crypto|Crypto]]
- [[02 - Topics/Programming|Programming]]

---

## Domains
| Domain | Folder |
|--------|--------|
| Commands | [[00 - Command Inbox/_README\|Inbox]] |
| Sessions | [[01 - Sessions]] |
| Topics | [[02 - Topics]] |
| Trading | [[03 - Trading]] |
| Projects | [[04 - Projects]] |
| Research | [[05 - Research]] |
| Ideas | [[06 - Ideas]] |
| Wiki | [[Wiki]] |
```

- [ ] **Step 2: Write INDEX.md**

```markdown
---
type: atlas
created: 2026-04-17
updated: 2026-04-17
---
# Glory's Intellect — Full Index

*Update this whenever a major new note is added.*

---

## Topics
- [[02 - Topics/Trading|Trading]]
- [[02 - Topics/Crypto|Crypto]]
- [[02 - Topics/Programming|Programming]]

## Trading
- [[03 - Trading/Watchlists/Main|Watchlist — Main]]

## Wiki
- [[Wiki/Trading-Glossary|Trading Glossary]]
- [[Wiki/Crypto-Glossary|Crypto Glossary]]

## Projects
*None yet*

## Research
*None yet*

## Ideas
*None yet*
```

- [ ] **Step 3: Verify both files render correctly in Obsidian**

Open HOME.md and confirm all links are valid (no broken wikilinks shown in red).

---

## Task 5: Seed Topic Pages

**Files:**
- Create: `02 - Topics/Trading.md`
- Create: `02 - Topics/Crypto.md`
- Create: `02 - Topics/Programming.md`

- [ ] **Step 1: Write Trading.md topic page**

```markdown
---
type: topic
created: 2026-04-17
updated: 2026-04-17
status: growing
tags: [trading, finance]
---
# Trading

## Overview
Trading is the active buying and selling of financial instruments — stocks, forex, crypto, futures, options — with the goal of generating profit from price movements.

## Key Concepts
- **Technical Analysis** — Reading price charts, patterns, indicators
- **Risk Management** — Position sizing, stop losses, R:R ratios
- **Market Structure** — Highs, lows, trends, ranges, support/resistance
- **Psychology** — Discipline, patience, emotional control
- **Edge** — A repeatable, statistical advantage in the market

## Strategies (linked)
*Add links to [[03 - Trading/Strategies]] as they are built out*

## Journal
All trades logged in [[03 - Trading/Journal]]

## Resources
- [[Wiki/Trading-Glossary|Trading Glossary]]
- [[02 - Topics/Crypto|Crypto]]

## Session History
- 2026-04-17 — Topic page created, vault initialized
```

- [ ] **Step 2: Write Crypto.md topic page**

```markdown
---
type: topic
created: 2026-04-17
updated: 2026-04-17
status: growing
tags: [crypto, blockchain, finance]
---
# Crypto

## Overview
Cryptocurrency is a digital asset secured by cryptography and operating on decentralized blockchain networks. Bitcoin launched the space in 2009; thousands of projects have followed.

## Key Concepts
- **Bitcoin (BTC)** — First and largest crypto, digital store of value
- **Ethereum (ETH)** — Programmable blockchain, home of DeFi and NFTs
- **Altcoins** — All non-Bitcoin cryptocurrencies
- **DeFi** — Decentralized Finance, financial services on-chain
- **Wallets** — Self-custody via seed phrases, hardware wallets
- **Exchanges** — CEX (Coinbase, Binance) vs DEX (Uniswap, Jupiter)
- **On-chain Analysis** — Reading blockchain data for market intelligence

## Resources
- [[Wiki/Crypto-Glossary|Crypto Glossary]]
- [[02 - Topics/Trading|Trading]]

## Session History
- 2026-04-17 — Topic page created, vault initialized
```

- [ ] **Step 3: Write Programming.md topic page**

```markdown
---
type: topic
created: 2026-04-17
updated: 2026-04-17
status: growing
tags: [programming, tech, tools]
---
# Programming

## Overview
Programming covers the languages, tools, frameworks, and patterns used to build software — from scripts and bots to full applications.

## Key Concepts
- **Languages** — Python, JavaScript, Bash, and others as needed
- **Automation** — Scripts that save time on repetitive tasks
- **APIs** — Connecting services and data sources programmatically
- **AI/LLMs** — Building with Claude, local models via LM Studio
- **Tools** — Claude Code, VS Code, Obsidian, Git

## Active Setup
- LM Studio running local models at `localhost:1234`
- Claude Code configured with `ANTHROPIC_BASE_URL=http://localhost:1234`
- Vault at `D:\Glory\Glory's Intellect`

## Session History
- 2026-04-17 — Topic page created, vault initialized
```

- [ ] **Step 4: Verify all three topic pages exist**

```bash
ls "D:\Glory\Glory's Intellect/02 - Topics/"
```
Expected: Trading.md, Crypto.md, Programming.md

---

## Task 6: Scaffold Trading Domain

**Files:**
- Create: `03 - Trading/Journal/_template.md`
- Create: `03 - Trading/Strategies/_template.md`
- Create: `03 - Trading/Watchlists/Main.md`
- Create: `03 - Trading/Analysis/_template.md`

- [ ] **Step 1: Write Journal template**

```markdown
---
type: trade
date: {{date}}
asset: 
direction: 
entry: 
exit: 
result: 
pnl: 
tags: []
---
# Trade — [ASSET] {{date}}

## Setup
<!-- What pattern/signal triggered the trade? -->

## Execution
<!-- Entry price, position size, stop loss, take profit -->

## Outcome
<!-- What actually happened, final P&L -->

## Lesson
<!-- What to repeat or avoid next time -->
```

- [ ] **Step 2: Write Strategies template**

```markdown
---
type: strategy
created: {{date}}
updated: {{date}}
status: active
winrate: 
avg-rr: 
tags: []
---
# Strategy: [Name]

## Overview
<!-- What is this setup? What market condition does it exploit? -->

## Entry Criteria
1. 
2. 
3. 

## Exit Criteria
- **Stop Loss:** 
- **Take Profit:** 
- **Trailing:** 

## Risk Management
- Position size: 
- Max risk per trade: 
- Max daily loss: 

## Examples
<!-- Link to journal entries where this played out -->

## Track Record
| Date | Asset | Result | Notes |
|------|-------|--------|-------|
```

- [ ] **Step 3: Write Watchlists/Main.md**

```markdown
---
type: watchlist
created: 2026-04-17
updated: 2026-04-17
tags: [trading, watchlist]
---
# Watchlist — Main

*Updated regularly. Add tickers/assets being monitored.*

## Crypto
| Asset | Notes | Priority |
|-------|-------|----------|
| BTC | Bitcoin — macro leader | High |
| ETH | Ethereum — altcoin beta | High |

## Stocks
| Asset | Notes | Priority |
|-------|-------|----------|

## Forex
| Pair | Notes | Priority |
|------|-------|----------|

---
*Last updated: 2026-04-17*
```

- [ ] **Step 4: Write Analysis template**

```markdown
---
type: analysis
created: {{date}}
asset: 
timeframe: 
bias: 
tags: []
---
# Analysis — [ASSET] {{date}}

## Market Context
<!-- Where is price in the bigger picture? Trend, range, key levels? -->

## Key Levels
- Resistance: 
- Support: 
- Current Price: 

## Bias
<!-- Bull / Bear / Neutral and why -->

## Scenarios
**Bull case:** 

**Bear case:** 

## Trade Ideas
<!-- Specific setups watching for -->
```

- [ ] **Step 5: Verify Trading domain is fully scaffolded**

```bash
find "D:\Glory\Glory's Intellect/03 - Trading/" -type f
```
Expected: Journal/_template.md, Strategies/_template.md, Watchlists/Main.md, Analysis/_template.md

---

## Task 7: Build Wiki Pages

**Files:**
- Create: `Wiki/Trading-Glossary.md`
- Create: `Wiki/Crypto-Glossary.md`

- [ ] **Step 1: Write Trading-Glossary.md**

```markdown
---
type: wiki
created: 2026-04-17
updated: 2026-04-17
tags: [trading, reference, glossary]
---
# Trading Glossary

## A
**Ask** — The lowest price a seller will accept.
**ATH** — All-Time High. The highest price an asset has ever reached.
**ATL** — All-Time Low.

## B
**Bid** — The highest price a buyer will pay.
**Breakout** — Price moving above a resistance level with conviction.
**Bull/Bear** — Bull = expecting price to rise. Bear = expecting price to fall.

## C
**Confluence** — Multiple signals/levels aligning at the same price zone.
**Consolidation** — A period of sideways price action after a trend.

## D
**Drawdown** — The decline from a peak to a trough in account value.

## E
**Edge** — A statistical advantage that produces positive expectancy over many trades.
**EMA** — Exponential Moving Average. Weighted more heavily toward recent prices.

## F
**FUD** — Fear, Uncertainty, Doubt. Negative sentiment.
**FOMO** — Fear Of Missing Out. Buying into a move too late.

## L
**Liquidity** — The ease with which an asset can be bought/sold without moving price.
**Long** — Buying an asset, profiting if price rises.

## M
**Market Structure** — The pattern of higher highs/lows (uptrend) or lower highs/lows (downtrend).
**Momentum** — The rate of price change. Strong momentum = fast, sustained moves.

## P
**Position Size** — The amount of capital allocated to a single trade.
**PnL** — Profit and Loss.

## R
**R:R** — Risk to Reward ratio. A 1:3 R:R means risking 1 to make 3.
**Resistance** — A price level where selling pressure has historically emerged.
**Risk Management** — The system for sizing positions and limiting losses.

## S
**Short** — Selling an asset you don't own, profiting if price falls.
**Stop Loss** — An order that closes a trade at a predetermined loss level.
**Support** — A price level where buying pressure has historically emerged.

## T
**Take Profit** — A predetermined exit point to lock in gains.
**Trend** — Sustained directional price movement.

## V
**Volume** — The number of units traded in a given period. Confirms moves.

## W
**Whipsaw** — A false breakout that reverses quickly.
```

- [ ] **Step 2: Write Crypto-Glossary.md**

```markdown
---
type: wiki
created: 2026-04-17
updated: 2026-04-17
tags: [crypto, blockchain, reference, glossary]
---
# Crypto Glossary

## A
**Altcoin** — Any cryptocurrency other than Bitcoin.
**APY** — Annual Percentage Yield. Return on DeFi positions.
**Airdrop** — Free token distribution to wallet holders.

## B
**Bitcoin (BTC)** — The first and largest cryptocurrency by market cap.
**Block** — A batch of transactions recorded on the blockchain.
**Blockchain** — A decentralized, immutable ledger of transactions.
**Bridge** — A protocol for moving assets between different blockchains.

## C
**CEX** — Centralized Exchange (Coinbase, Binance, Kraken).
**Cold Wallet** — Offline storage for crypto. Most secure.
**Confirmation** — When a transaction is added to a block and verified.

## D
**DAO** — Decentralized Autonomous Organization. Community-governed protocol.
**DeFi** — Decentralized Finance. Financial services on-chain without intermediaries.
**DEX** — Decentralized Exchange (Uniswap, Jupiter, dYdX).

## E
**Ethereum (ETH)** — Programmable blockchain. Home of DeFi, NFTs, smart contracts.

## G
**Gas** — The fee paid to process a transaction on a blockchain.

## H
**HODL** — Hold On for Dear Life. Long-term holding strategy.
**Hot Wallet** — Online/connected wallet. Convenient but less secure.

## L
**Layer 1 (L1)** — Base blockchain (Bitcoin, Ethereum, Solana).
**Layer 2 (L2)** — Scaling solution built on top of L1 (Arbitrum, Optimism).
**Liquidity Pool** — Funds locked in a DeFi contract to enable trading.

## M
**Market Cap** — Total value of a cryptocurrency (price × circulating supply).
**Mempool** — Waiting room for unconfirmed transactions.
**Mnemonic / Seed Phrase** — 12 or 24 words that back up a crypto wallet.

## N
**NFT** — Non-Fungible Token. Unique digital asset on-chain.
**Node** — A computer that validates and relays blockchain transactions.

## P
**Private Key** — The cryptographic key that proves ownership of a wallet.
**Protocol** — A set of rules governing a blockchain or DeFi application.

## S
**Seed Phrase** — 12-24 word backup for a crypto wallet. Never share this.
**Smart Contract** — Self-executing code on a blockchain.
**Solana (SOL)** — High-speed L1 blockchain. Home of many DeFi and trading apps.
**Stablecoin** — Crypto pegged to a fiat currency (USDC, USDT, DAI).

## W
**Wallet** — Software or hardware that stores private keys and manages crypto.
**Web3** — The decentralized internet built on blockchain technology.
**Whale** — A large holder who can move markets.

## Y
**Yield Farming** — Earning returns by providing liquidity to DeFi protocols.
```

- [ ] **Step 3: Verify Wiki folder**

```bash
ls "D:\Glory\Glory's Intellect/Wiki/"
```
Expected: Trading-Glossary.md, Crypto-Glossary.md, Untitled.md (existing)

---

## Task 8: Today's Session Log

**Files:**
- Create: `01 - Sessions/2026-04-17.md`

- [ ] **Step 1: Write the session log**

```markdown
---
type: session
created: 2026-04-17
tags: [vault-setup, init]
topics-touched: [Trading, Crypto, Programming]
---
# Session — 2026-04-17

## Commands Run
- Vault initialization and build-out

## Research Done
- Vault architecture design
- Obsidian folder structure best practices

## Decisions Made
- Option C (Glory's Native System) chosen for vault architecture
- True second-brain scope (all domains)
- Bidirectional + command-driven interaction model
- Wiki folder included per user request

## Notes Created
- [[07 - Atlas/HOME|HOME]] — Vault front door
- [[07 - Atlas/INDEX|INDEX]] — Full vault map
- [[02 - Topics/Trading|Trading]] — Topic page
- [[02 - Topics/Crypto|Crypto]] — Topic page
- [[02 - Topics/Programming|Programming]] — Topic page
- [[03 - Trading/Watchlists/Main|Watchlist — Main]]
- [[Wiki/Trading-Glossary|Trading Glossary]]
- [[Wiki/Crypto-Glossary|Crypto Glossary]]
- All templates created in [[08 - Templates]]
```

---

## Task 9: Configure Obsidian Startup

**Files:**
- Modify: `.obsidian/app.json`

- [ ] **Step 1: Read current app.json**

Read `D:\Glory\Glory's Intellect/.obsidian/app.json`

- [ ] **Step 2: Add startup file setting**

Add `"defaultViewMode": "preview"` and set the initial file to HOME.md by updating app.json to include:

```json
{
  "defaultViewMode": "preview"
}
```

Note: Obsidian sets the startup file via the workspace.json (last open file) and by pinning HOME.md as the default. After building, open Obsidian, navigate to `07 - Atlas/HOME.md`, and set it as the startup note via: Settings → Options → Files & Links → Default new note location.

- [ ] **Step 3: Verify Obsidian opens to HOME.md**

Open Obsidian with the vault. Confirm the file explorer shows all new folders and HOME.md is accessible.

---

## Task 10: Link Raw Sources

**Files:**
- Modify: `raw-sources/Glorys Intellect.md`
- Modify: `raw-sources/Trading.md`

- [ ] **Step 1: Update Glorys Intellect.md with vault links**

Add frontmatter and a link to HOME at the top of the existing file:

```markdown
---
type: source
created: 2026-04-17
tags: [meta, foundation]
---
# Glory's Intellect — Foundation

*This is the founding document. The full vault lives at [[07 - Atlas/HOME|HOME]].*

---

[original content below]
```

- [ ] **Step 2: Update Trading.md raw source**

```markdown
---
type: source
created: 2026-04-17
tags: [trading, source]
---
# Trading — Raw Source

*Full trading knowledge lives at [[02 - Topics/Trading|Trading Topic Page]].*
*Trade journal: [[03 - Trading/Journal/_template|Journal]]*
*Watchlist: [[03 - Trading/Watchlists/Main|Main Watchlist]]*
```

- [ ] **Step 3: Final verification — full file count**

```bash
find "D:\Glory\Glory's Intellect/" -name "*.md" | grep -v ".obsidian" | sort
```
Expected: 20+ markdown files across all folders.

---

## Self-Review Checklist

- [x] Folder structure: all 10 domains created (Task 1)
- [x] Templates: all 8 types covered (Task 2)
- [x] Command Inbox: README with usage instructions (Task 3)
- [x] Atlas: HOME.md and INDEX.md (Task 4)
- [x] Topic pages: Trading, Crypto, Programming seeded (Task 5)
- [x] Trading domain: Journal, Strategies, Watchlists, Analysis (Task 6)
- [x] Wiki: Trading Glossary, Crypto Glossary (Task 7)
- [x] Session log: today's session documented (Task 8)
- [x] Obsidian config: startup note guidance (Task 9)
- [x] Raw sources: linked into new structure (Task 10)
- [x] Wiki folder explicitly included (user requirement)
- [x] No TBDs or placeholders in any file content
- [x] All wikilinks use correct paths
