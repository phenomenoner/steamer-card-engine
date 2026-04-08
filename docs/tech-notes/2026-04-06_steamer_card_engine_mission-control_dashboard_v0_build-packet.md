# 2026-04-06 — steamer-card-engine Mission Control Dashboard v0 build packet

> Update 2026-04-09: the committed dashboard fixture index is no longer March-only. The backend now discovers representative `manual-live-paired-*` compare bundles as well as the original `replay-sim_*` fixtures, yielding browser dates from `2026-03-06` through `2026-04-08`. The surface is still **one representative compare bundle per session date**; same-date variants remain collapsed.

## Verdict

The right product cut is a **read-only browser Mission Control dashboard** for `steamer-card-engine`, not a broker-facing GUI and not a generic SaaS analytics page.

Its job is to turn existing replay/compare artifacts into a **daily battle report + strategy-card observability surface + replay drilldown surface** that an operator can open from the parent system browser and understand in about 10 seconds.

## Why now

The real gate is no longer “can card-engine emit comparable bundles?”
That gate is already closed enough to support a new product edge:

- committed replay-sim baseline/candidate bundle emission -> compare receipt already exists at the repo level
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

### A. Demoable committed compare bundles
Committed comparison directories already exist for the original replay-sim March set plus recent paired-live representatives across:
- `2026-03-06`
- `2026-03-10`
- `2026-03-12`
- `2026-03-20`
- `2026-03-24`
- `2026-03-25`
- `2026-03-26`
- `2026-03-27`
- `2026-03-30`
- `2026-03-31`
- `2026-04-01`
- `2026-04-02`
- `2026-04-08`

Representative pass receipts:
- `comparisons/replay-sim_tw-paper-sim-twse-2026-03-12-full-session_baseline_20260315T082719Z__replay-sim_tw-paper-sim-twse-2026-03-12-full-session_candidate_20260315T082719Z/summary.md`
- `comparisons/manual-live-paired-20260320-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260320T012107Z/summary.md`
- `comparisons/manual-live-paired-20260408-entry-mode-long-one-vcp-vcp-min-trend-slope-10-tick-volume-mode-auto-feed-neoapitest-20260408T010601Z/summary.md`

### B. Demoable bundle inputs already on disk
For those committed dashboard dates, the repo already has:
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

Topology note:
- unchanged; this packet originally recut the opening demo contract to the committed March set, and the current implementation now truthfully expands discovery to representative paired-live dates through `2026-04-08`

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

Using the committed replay-sim + paired-live lineage, the current demo can truthfully ship these pages:

1. **History index** over representative dates from `20260306` through `20260408`
2. **Daily command view** for the current hero day `20260408`
3. **Strategy-card detail** for dates that actually carry card/intents data (for example the March replay fixtures)
4. **Replay / event timeline** backed by local bundle event logs, including paired-live event-only days
5. **Transaction/PnL panel** with a truthful zero-state contract where compare-lane trade surfaces remain empty

If we want one explicit “receipt wall” demo panel, use either:
- the 2026-03-12 replay compare-manifest / diff / summary triple, or
- a recent manual-live representative such as `2026-04-08`

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

## API surface v0 (extended, backwards-compatible)

Primary deck-native surfaces:
- `GET /api/dates` (deck wall / day covers)
- `GET /api/days/{date}/deck` (Mission Control -> Daily Deck projection)
- `GET /api/days/{date}/lanes/{lane}/cards/{card_id}` (strategy-card detail surface)

Legacy v0 surfaces (still supported):
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
- fixture selection for the committed representative date index (`20260306` → `20260408`)
- parse tests for bundle discovery across replay-sim and manual-live compare families
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

Use the committed replay-sim + paired-live lineage as the truthful demo fixture set and execute the dashboard as a **櫻花刀舞 serial queue**:

1. fixture contract
2. day-bundle aggregator
3. read-only API
4. React shell
5. daily command view
6. strategy-card detail
7. replay / anomaly drilldown
8. polish + handoff
