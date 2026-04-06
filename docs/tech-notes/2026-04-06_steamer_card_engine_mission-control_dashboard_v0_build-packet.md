# 2026-04-06 — steamer-card-engine Mission Control Dashboard v0 build packet

## Verdict

The right product cut is a **read-only browser Mission Control dashboard** for `steamer-card-engine`, not a broker-facing GUI and not a generic SaaS analytics page.

Its job is to turn existing live-sim / compare artifacts into a **daily battle report + strategy-card observability surface + replay drilldown surface** that an operator can open from the parent system browser and understand in about 10 seconds.

## Why now

The real gate is no longer “can card-engine emit comparable bundles?”
That gate is already closed enough to support a new product edge:

- same-day AWS live-sim capture -> local sync -> baseline/candidate bundle emission -> compare receipt already exists at the manual smoke level
- the repo already contains multi-day local `runs/` and `comparisons/` bundles
- CK now wants a human-first browser surface similar to `pm-dashboard`, but aimed at Steamer live-sim snapshots, strategy cards, transaction surfaces, and date-based historical review

So the next honest move is **observability productization**, not another round of hidden plumbing.

## Whole-picture promise

The dashboard should let an operator / trader / reviewer answer four questions fast:

1. what happened today?
2. which strategy card or lane dominated behavior?
3. did anything abnormal happen?
4. what is worth drilling into?

Fake progress would be:

- shipping a pretty shell without a truthful day-bundle contract
- adding real-time theater before the daily battle report is clear
- letting the frontend assemble raw logs itself instead of reading a normalized read-only projection
- pretending transaction / PnL richness exists where the current compare contract still only carries zeroed placeholders

## Repo / remote decision

This product line should live in **`steamer-card-engine`** and push to its existing remote:

- repo: `/root/.openclaw/workspace/steamer-card-engine`
- remote: `origin https://github.com/phenomenoner/steamer-card-engine.git`

Why this repo, not Steamer core:

- `steamer-card-engine` already owns the backtest-engine / productization surface
- the dashboard is a product-adjacent observability surface over card-engine artifacts
- native Steamer daily control-plane truth still remains upstream in Steamer; this dashboard must not pretend to replace that

## Demo-first truth surfaces available today

### A. Manual same-day AWS paired-live smoke receipt
- tech note:
  - `docs/tech-notes/2026-03-20_steamer_card_engine_manual_paired_live_compare_smoke.md`
- proves:
  - same-day AWS sim capture
  - local sync
  - paired baseline/candidate bundle emission
  - passing compare receipts

### B. Demoable recent local compare bundles
Recent comparison directories already exist, including:
- `comparisons/manual-live-paired-20260331-...`
- `comparisons/manual-live-paired-20260401-...`
- `comparisons/manual-live-paired-20260402-...`

Representative pass receipts:
- `comparisons/manual-live-paired-20260402-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260402T010536Z/summary.md`
- `comparisons/manual-live-paired-20260402-entry-mode-long-one-vcp-vcp-min-trend-slope-2-tick-volume-mode-auto-feed-neoapitest-20260402T010536Z/summary.md`

### C. Demoable bundle inputs already on disk
For the recent days above, the repo already has:
- `runs/.../event-log.jsonl`
- `runs/.../intent-log.jsonl`
- `runs/.../feature-provenance.jsonl`
- `runs/.../config-snapshot.json`
- `runs/.../pnl-summary.json`
- `runs/.../anomalies.json`
- `runs/.../scenario-spec.json`
- `comparisons/.../compare-manifest.json`
- `comparisons/.../diff.json`
- `comparisons/.../summary.md`

### Important truth boundary for demo
Current comparison bundles are excellent for:
- page skeletons
- day summaries
- strategy-card and scenario identity surfaces
- anomaly / compare / provenance drilldowns
- replay/event timeline demo

Current bundles are **not yet rich** for a deep trading blotter because:
- recent compare receipts still show zeroed counts for fills/orders/intents/risk in the decision-grade diff summary
- recent `pnl-summary.json` files are effectively zeroed for the compare lane

Therefore the opening browser demo should be framed as:
- **battle report + strategy-card observability + replay/snapshot explorer first**
- transaction / PnL panels included, but rendered truthfully with zero-state / placeholder-state contracts where data is not yet present

## Product cut

### What this is
- read-only browser dashboard
- production-grade UI/UX
- React frontend
- FastAPI backend
- normalized day-bundle aggregator
- historical date switching
- parent-system browser-openable

### What this is not
- broker control plane
- live order entry UI
- replacement for CLI/operator authority surfaces
- replacement for Steamer native daily control-plane truth

## Architecture cut

### Frontend
- React + TypeScript
- Tailwind + shadcn/ui or Radix primitives
- TanStack Query
- TanStack Table
- Recharts or Visx

### Backend
- FastAPI read-only API
- one local data-aggregator layer
- no write-back into runtime / broker / Steamer daily controllers

### Data flow
`raw bundle files -> normalized day projection -> cached day bundle -> REST API -> React UI`

### Aggregator responsibilities
1. map raw files into stable domain objects
2. compute daily summary and strategy-card summaries
3. compute anomaly and compare summaries
4. expose snapshot/replay drilldown references
5. preserve truthful empty-state markers where runtime data is absent

## Primary page map

### 1. Daily Command View (`/`)
Primary page. Must answer the battle-picture immediately.

Top band:
- selected date
- scenario / lane summary
- compare status
- anomaly count
- dominant card / dominant lane
- realized outcome status (including truthful zero-state)

Main body:
- strategy-card leaderboard
- compare posture summary (baseline vs candidate)
- anomaly panel
- event/replay timeline
- transaction/PnL panel with truthful empty state if not populated

### 2. Strategy Card View (`/cards`)
- strategy card identity
- card content / config summary
- trigger counts
- reason distribution
- related anomalies
- related events on timeline

### 3. Replay / Snapshot View (`/replay`)
- event timeline scrubber
- event detail drawer
- config / scenario snapshot
- feature provenance and decision-context drilldown

### 4. History View (`/history`)
- date index
- recent sessions list
- compare pass/fail / anomaly counts
- date-to-date switch and quick compare selection

## Demo pages that are truthful right now

Using the recent AWS paired-live capture lineage, the first demo should explicitly ship these pages:

1. **History index** over `20260331`, `20260401`, `20260402`
2. **Daily command view** for `20260402`
3. **Strategy-card detail** for slope `10` and slope `2` lanes
4. **Replay / event timeline** backed by local bundle event logs
5. **Transaction/PnL panel** with a truthful zero-state contract where compare-lane trade surfaces remain empty

If we want one explicit “receipt wall” demo panel, use:
- the 2026-03-20 manual paired-live smoke note
- the 2026-04-02 compare-manifest / diff / summary triple

## UI/UX posture

The visual language should read like a **tactical control room**, not crypto-casino trading UI and not generic B2B SaaS.

Hard UI rules:
- decision density over marketing emptiness
- hierarchy first: battle picture -> card leadership -> anomalies -> replay -> receipts
- subtle motion only
- drawers for drilldown, not page explosion
- use empty states as truth surfaces, not embarrassment screens

Recommended tone:
- dark graphite / slate base
- emerald for green status
- red/crimson for risk
- steel neutrals for background structure
- one restrained accent for active focus

## API surface v0

- `GET /api/dates`
- `GET /api/days/{date}/summary`
- `GET /api/days/{date}/cards`
- `GET /api/days/{date}/compare`
- `GET /api/days/{date}/events`
- `GET /api/days/{date}/transactions`
- `GET /api/days/{date}/snapshots/{id}`

The contract for `transactions` must allow:
- populated records when present
- truthful `empty_reason` metadata when absent in the selected bundle

## Opening bounded slice

The first slice should prove one thing only:

> one recent day can be opened in browser and read as a coherent battle report backed by real local artifacts.

That slice includes:
- date switcher
- daily summary strip
- compare summary
- strategy-card leaderboard
- anomaly panel
- event timeline
- transaction/PnL empty-state contract

It explicitly excludes:
- websocket/live streaming
- auth system redesign
- broker actions
- deep multi-day analytics
- per-tick fancy charting

## Verifier plan

### Backend / aggregator
- fixture selection for `20260331`, `20260401`, `20260402`
- parse tests for bundle discovery
- summary generation tests
- empty-state correctness tests for transactions/PnL
- missing-file behavior tests

### API
- contract tests for all read-only endpoints
- 404 on missing date
- explicit `empty_reason` instead of silent blank arrays when appropriate

### Frontend
- browser smoke: load dashboard -> switch date -> open card drawer -> open replay detail
- screenshot baseline for first screen
- cognition check: 10-second operator readability

## Topology check

- runtime topology changed: **no**
- scheduler / cron topology changed: **no**
- authority split changed: **no**
- product scope changed: **yes, narrowly**
  - a read-only browser observability surface is now accepted as a product-adjacent line inside `steamer-card-engine`
  - it does **not** replace CLI/operator authority or Steamer native control-plane truth

## Next recommended move

Use the paired-live AWS capture lineage as the first truthful demo fixture set and execute the dashboard as a **櫻花刀舞 serial queue**:

1. fixture contract
2. day-bundle aggregator
3. read-only API
4. React shell
5. daily command view
6. strategy-card detail
7. replay / anomaly drilldown
8. polish + handoff
