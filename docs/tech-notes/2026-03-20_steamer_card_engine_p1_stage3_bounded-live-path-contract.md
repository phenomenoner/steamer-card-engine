# 2026-03-20 — steamer-card-engine P1 stage-3: bounded live path contract (disarmed live-capable → armed-live)

This note defines the **bounded live path** required for Product Sprint P1.

Boundary:
- contract-only; it does not claim the live execution lane is implemented today.
- it must not blur Product Sprint P1 with Sprint A ownership.
- it must not imply broad production readiness.

## Goal

Define one explicit, operator-credible path from the current product posture ladder into **bounded live capability**:

- the runtime may hold credentials that are *capable* of trading (`trade_enabled=true`),
- but must remain **disarmed by default**,
- and must only become **armed-live** through an explicit operator action that is bounded in scope + time,
- with an always-available operator flatten/disarm exit.

## Inputs (existing truth)

- capability vs posture ladder: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage1_capability-posture-contract.md`
- operator control contract: `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-19_steamer_card_engine_p1_stage2_operator-control-contract.md`
- product scope boundary: `steamer-card-engine/docs/PRODUCT_SCOPE.md`
- auth/session capability semantics: `steamer-card-engine/docs/AUTH_AND_SESSION_MODEL.md`
- day-trading exits vocabulary: `steamer-card-engine/docs/DAYTRADING_GUARDRAILS.md`
- CLI command families (including operator surface placeholders): `steamer-card-engine/docs/CLI_SPEC.md`

## One bounded live path (contract target)

### A) Preflight: prove capability without arming posture

1) Operator inspects profile + expected capability shape (no login required):
   - `steamer-card-engine auth inspect-profile <profile>`

2) Runtime session is established (implementation detail is out of scope here), and the operator can inspect logical session state:
   - `steamer-card-engine auth inspect-session --json`

Hard invariant:
- It must be possible for the operator to see `trade_enabled=true` while `armed_live=false`.
- The product must never treat `trade_enabled=true` as "live trading is happening".

### B) Runtime steady-state: live-capable but disarmed

In this state:
- `mode=live`
- `capabilities.trade_enabled` may be `true`
- `armed_live=false`

Required behavior:
- broker/order submission surfaces must refuse to submit any order while disarmed.
- refusal must be explicit (not silent): the operator must be able to see that orders were blocked due to posture.

### C) Operator arm-live: bounded, time-limited authority

Operator transitions into armed-live using a command with explicit scope + TTL.

Contract target:
- `steamer-card-engine operator arm-live --deck <deck_id|deck_name> --ttl-seconds <N> [--operator-note <text>] ...`

Required guards (must be checked and reported):
- session health is OK
- `capabilities.trade_enabled=true` (else refuse with posture/capability mismatch)
- deck identity resolves to a concrete deck artifact
- TTL is present and within policy bounds (policy values may live in config; the existence of a bound is the requirement here)

Required outputs (JSON mode):
- `armed_live=true`
- `armed_scope` populated (deck + account + `armed_at` + `expires_at|ttl_seconds`)

### D) While armed: receipts + immediate exits are first-class

While `armed_live=true`:
- every order submission must carry enough provenance to be audited back to:
  - `session_id` + `account_no`
  - `deck_id|deck_name`
  - current `armed_scope`
- the operator must be able to disarm immediately:
  - `steamer-card-engine operator disarm-live`
- the operator must be able to flatten using a named exit policy mode:
  - `steamer-card-engine operator flatten --mode emergency|forced-exit|final-auction`

Hard rules:
- `disarm-live` must stop further order submissions immediately.
- `flatten` may implicitly disarm; if it does, that must be explicit in the receipt.

### E) TTL expiry: auto-disarm is mandatory

When the arm TTL expires:
- posture must automatically revert to `armed_live=false`.
- the operator must be able to observe this transition in `operator status --json`.

## Observability + audit (contract target)

Minimum operator-inspectable surfaces:

- `steamer-card-engine operator status [--json]`
  - includes capabilities (`trade_enabled`) and posture (`armed_live`, `armed_scope`) in one view.

- operator action receipts
  - arm/disarm/flatten actions are recorded with who/when/scope/why (operator note)
  - these receipts are required even if the runtime is still early/seed-grade.

## What this does NOT claim

- It does not claim the broker adapter is production-ready.
- It does not claim the operator commands are already implemented.
- It does not widen scope into strategy selection, universe research, or Sprint A's pair-contract milestones.

## Stage-3 closure criteria (P1)

Stage-3 is considered closed when repo truth contains one coherent bounded-live-path contract that:
- explicitly connects capability (`trade_enabled`) + posture (`armed_live`) + operator exits (`disarm`, `flatten`), and
- names a time-bounded arming mechanism (TTL) with mandatory auto-disarm, and
- remains explicit that live authority is operator-governed and auditable (no hidden live posture).

Topology note:
- this note changes docs truth only; it does not change runtime topology or scheduler posture.
