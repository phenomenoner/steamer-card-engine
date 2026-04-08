# 2026-04-08 — steamer-card-engine market-phase gating gap (backlog note)

## Why this note exists

A dashboard truth check on fixture day `2026-03-12` raised two product-level questions:

1. should the engine honor the full TW cash intraday session contract (`09:00–13:30 Asia/Taipei`) rather than silently reflecting whatever partial source window happened to be captured?
2. should execution semantics distinguish **盤前試搓 / quote-driven pre-open** from **正式開盤後的實際交易**, including the Taiwan-specific constraint that pre-open orders are not treated like normal intraday execution and should default to stricter order-style rules (for example ROD-only) unless a strategy explicitly opts in?

This note captures the current truth and freezes the follow-up as a bounded backlog slice.

## What repo truth says today

### 1) Session contract exists at the spec layer

The repo already declares the canonical full-session slice for TWSE intraday scenarios:

- `docs/SCENARIO_SPEC.md`
- `src/steamer_card_engine/sim_compare.py:511-515`

Both point to:
- `start_local = 09:00:00`
- `end_local = 13:30:00`

So the **contract surface** does already say full session.

### 2) Actual emitted run timing still follows source min/max, not the full-session contract

In `src/steamer_card_engine/sim_compare.py`, the bundle emitter derives:

- `run-manifest.json.started_at_utc`
- `run-manifest.json.ended_at_utc`
- `market_event_source.time_range.start/end`

from observed `min_event_time` / `max_event_time` in the consumed source rows.

That means a committed replay/live-sim bundle may truthfully represent a **partial observed source window** even when its `scenario-spec.json` says `full-session`.

Observed fixture proof (`2026-03-12`, candidate lane):
- `scenario-spec.json.session_slice = 09:00:00 → 13:30:00`
- `run-manifest.json.market_event_source.time_range = 08:31:42 → 09:04:47` (Asia/Taipei)

So the current system does **not** enforce “full session must actually be covered” at runtime/bundle-emission level.

### 3) Market-phase semantics are not implemented in the current execution path

There is a type-level hint that the product expects richer market-event semantics:

- `src/steamer_card_engine/adapters/base.py`
  - `MarketEvent.event_type: Literal["tick", "quote", "trade", "session"]`

But the M1/Mission-Control path does not operationalize those semantics.

Current replay normalizer behavior in `src/steamer_card_engine/sim_compare.py`:
- event rows are copied into `event-log.jsonl`
- `event_type` is passed through as raw metadata (`row.get("event_type") or row.get("raw_event") or "market_tick"`)
- no logic branches on quote vs trade vs session-open/session-close markers
- no market-phase classifier is emitted
- no session-window gate is applied before turning `entry` decisions into execution requests

### 4) `entry + ok` currently becomes an execution request without pre-open gating

Current behavior in `src/steamer_card_engine/sim_compare.py:430-449`:
- when `stage == "entry" and ok`
- emit `execution-log.jsonl` row immediately
- `order_type = "market"`
- no check for:
  - official open signal
  - first actual trade print after the open
  - pre-open trial-match state
  - pre-open order-style restriction (for example ROD-only)
  - strategy opt-in for pre-open participation

So today the repo does **not** implement the intended TW cash market-phase execution logic.

### 5) Close-side guardrails exist in docs/config, but open-side phase gating does not yet

Existing truth already covers some close-side behavior:
- `docs/DAYTRADING_GUARDRAILS.md`
- `examples/config/global.toml`

These include:
- intraday forced exit
- final-auction flatten window (`13:25–13:30`)
- reverse-side limit / ROD order style for final auction

That means the repo already acknowledges time-window-sensitive order-style logic near the close.
The symmetrical **open-side / pre-open-phase** trading logic is the missing half.

## Product verdict

The current repo truth is:

- **Yes**: the product contract says TWSE full-session should mean `09:00–13:30`.
- **No**: current emitted fixtures/bundles do not guarantee full-session coverage.
- **No**: current execution/request emission does not distinguish 盤前試搓 vs 正式開盤後實際交易.
- **No**: current code does not enforce a default “pre-open only ROD and only when strategy/policy explicitly allows it” rule.

## Backlog cut (requested follow-up)

Add a bounded P1 follow-up slice:

### `market-phase-gating-and-open-confirmation-v0`

Goal:
- make TW cash market-phase semantics explicit and testable before any stronger live-capability claim

Issue split:

#### Issue 1 — runtime / artifact market-phase gating

Problem:
- current replay/live-sim artifact emission can record pre-09:00 `execution-request` rows as if they were normal intraday attempts

Primary files for the eventual cut:
- `src/steamer_card_engine/sim_compare.py`
- `tests/test_sim_compare.py`
- likely new shared phase/session helper module under `src/steamer_card_engine/` (name to be decided during implementation packet)
- possibly `docs/SCENARIO_SPEC.md` / `docs/SIM_ARTIFACT_SPEC.md` if the emitted truth surface changes

Acceptance target:
1. a market-phase classifier exists for at least:
   - `pre_open_trial_match`
   - `regular_session_open`
   - `regular_session`
   - `final_auction`
   - `session_closed`
2. execution-request emission is gated by market phase
3. default policy blocks normal intraday entry before official open
4. pre-open participation requires explicit strategy/deck opt-in
5. when pre-open participation is enabled, allowed order styles are explicitly constrained (starting default: `ROD` only)
6. a `full-session` scenario whose source coverage does not actually span the declared session window can be flagged truthfully in emitted artifacts / validation
7. replay-sim and captured-baseline-dir live-sim must share the same generalized session-phase contract downstream of the event-source adapter edge
8. post-development verification must include a bounded historical tick-data ladder that checks phase-trace consistency across replay-sim and live-sim, plus truthful dashboard treatment of phase-derived fields

#### Issue 2 — dashboard truth surface for pre-open attempts

Problem:
- current Mission Control surfaces pre-open execution attempts as ordinary execution evidence instead of phase-aware or contract-violation-aware evidence

Primary files for the eventual cut:
- `src/steamer_card_engine/dashboard/aggregator.py`
- `frontend/src/App.tsx`
- `tests/test_dashboard.py`
- possibly dashboard-oriented docs / packet notes if the evidence contract changes

Acceptance target:
1. dashboard / receipts can distinguish:
   - quote / trial-match evidence
   - official-open / session event evidence
   - execution request attempts
   - actual order lifecycle / fill evidence
2. pre-open attempts from legacy / already-emitted artifacts are not rendered as normal regular-session execution evidence
3. the dashboard truth surface makes the phase state or contract violation explicit rather than silently hiding the ambiguity

Implementation-planning packet:
- `/root/.openclaw/workspace/steamer-card-engine/ops/execution-packets/2026-04-08_steamer-card-engine_market-phase-gating-and-dashboard-truth.packet.md`

Legacy-reconciliation rule:
- reconcile the legacy bot's all-session semantics into a **generalized session-phase contract** first; preserve phase/order-routing truths, but do not hardcode legacy timing/order literals as engine DNA

## Topology statement

- runtime/system topology: unchanged
- live cron/controller topology: unchanged
- product contract truth / backlog clarity: changed
