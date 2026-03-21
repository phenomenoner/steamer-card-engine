# 2026-03-19 — steamer-card-engine P1 stage-2: operator control contract (status / arm / disarm / flatten)

This note defines the **operator control contract** required for Product Sprint P1.

Boundary:
- contract-only; it does not claim the operator execution lane is implemented today.
- operator controls must remain **guarded and auditable**.

## Non-negotiable invariants

1) **No hidden live authority**
   - capability (`trade_enabled`) and posture (`armed_live`) must be distinct and inspectable.

2) **Disarmed is the default**
   - the runtime must start in a disarmed posture after boot and after session reconnects.

3) **Arm is explicit + bounded**
   - arming live must bind to an explicit scope (at least: deck identity + account identity + a time/TTL constraint).

4) **Flatten is always available to the operator**
   - if flatten is invoked, it must override card intent generation and drive the bounded exit policy.

5) **Disarm is immediate**
   - disarm must be able to stop further order submissions immediately (even if some orders are already in-flight).

## State model (contract target)

Minimum posture fields (readable in both human + `--json` forms):
- `mode`: `replay-sim` | `live-sim` | `live`
- `session_id`, `account_no`, `auth_mode`
- `capabilities`: `marketdata_enabled`, `account_query_enabled`, `trade_enabled`
- `armed_live`: boolean
- `armed_scope`: object (only when `armed_live=true`)
  - `deck_id` or `deck_name`
  - `account_no`
  - `armed_at`
  - `expires_at` (or `ttl_seconds`)
  - optional: `operator_note`
- `health_status`: coarse runtime health + session health

Hard rule:
- `trade_enabled=true` + `armed_live=false` must be a *first-class, non-ambiguous* state.

## CLI surfaces (contract target)

Reference: `steamer-card-engine/docs/CLI_SPEC.md`.

### `steamer-card-engine operator status`
Purpose:
- show the **truth** of session capability + live posture.

Required output fields (JSON mode):
- all state model fields above
- last N operator actions summary (optional)

### `steamer-card-engine operator arm-live ...`
Purpose:
- transition `armed_live: false -> true`.

Preconditions (must be checked and reported):
- session is healthy
- `trade_enabled=true` (or explicitly refuse with a clear error that capability is missing)
- explicit target deck identity is provided and validated

Guards:
- require explicit confirmation flags for non-dry-run usage (contract TBD; must not be implicit).
- bind a TTL (`--ttl-seconds` or equivalent)

Receipts:
- write an operator action receipt entry containing: who/when/what scope/why (operator note)

### `steamer-card-engine operator disarm-live`
Purpose:
- transition `armed_live: true -> false`.

Receipt:
- record the disarm action and whether any in-flight orders were still pending.

### `steamer-card-engine operator flatten [--mode ...]`
Purpose:
- force exit posture; it is acceptable for this to implicitly disarm.

Modes (aligned to `DAYTRADING_GUARDRAILS.md`):
- `emergency`
- `forced-exit`
- `final-auction`

Receipt:
- record flatten request + selected mode + resulting exit action plan.

## Exit codes (contract target)

- `0`: success
- `1`: general failure / unhandled
- `4`: operator action refused due to posture/capability mismatch (new; reserve)
- `5`: operator action refused due to missing confirmation/approval flags (new; reserve)

(Do not change existing sim/validation exit-code meanings.)

## Mapping to existing repo docs (so we don't lie about authority)

- `steamer-card-engine/docs/AUTH_AND_SESSION_MODEL.md` already defines the capability fields (`marketdata_enabled`, `trade_enabled`, `account_query_enabled`) and requires that the CLI expose them; this stage-2 contract extends that surface with an explicit operator-governed posture bit (`armed_live`) plus a bounded `armed_scope`.
- `steamer-card-engine/docs/CLI_SPEC.md` already names the operator command family (`operator status|arm-live|disarm-live|flatten`); this note defines the minimum **contract target** for their state fields, preconditions, and refusal/exit-code semantics, without claiming the runtime is implemented today.
- `steamer-card-engine/docs/DAYTRADING_GUARDRAILS.md` defines the vocabulary for flatten/exit policy; this note binds operator `flatten --mode` to those named modes.

## Stage-2 closure criteria (P1)

Stage-2 is considered closed when:
- the above operator control surfaces and state model are explicit in repo truth, and
- the contract is clearly mapped to the existing CLI spec and auth/session model, with no ambiguity about live authority.

Topology note:
- writing this contract note changes docs truth only; it does not change runtime topology or live scheduler posture.
