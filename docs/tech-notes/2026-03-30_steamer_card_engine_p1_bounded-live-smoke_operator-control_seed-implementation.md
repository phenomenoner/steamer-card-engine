# 2026-03-30 — steamer-card-engine P1 bounded-live smoke: operator-control seed implementation

## Why this slice landed

The bounded-live path contract named a concrete gate: operator control posture must be executable enough to prove
`trade_enabled` and `armed_live` are distinct, with explicit refusal while disarmed and auditable receipts.

This slice implements that gate as a **seed local control plane**, without claiming broker-connected live execution.

## What is now executable

- `steamer-card-engine operator status [--json]`
  - returns capability + posture in one view
  - includes `order_submission_gate` (`allowed` + explicit reason)
  - applies TTL expiry check and triggers auto-disarm receipt if needed

- `steamer-card-engine operator arm-live --deck ... --ttl-seconds ... --auth-profile ... --confirm-live`
  - requires explicit confirmation flag (`--confirm-live`)
  - requires `trade_enabled=true` from the chosen auth profile
  - resolves deck to a concrete manifest path
  - enforces bounded TTL policy

- `steamer-card-engine operator disarm-live`
  - immediate disarm posture transition
  - emits receipt

- `steamer-card-engine operator flatten --mode emergency|forced-exit|final-auction`
  - always available
  - may implicitly disarm (explicit in receipt)

- `steamer-card-engine operator submit-order-smoke --symbol ... --side ... --quantity ...`
  - seed smoke command to verify order-gate behavior
  - returns explicit refusal while disarmed (`exit=4`) with receipt
  - when armed, captures acceptance receipt but does **not** submit to broker

## Receipt/state surfaces

- state file (default): `.state/operator_posture.json`
- receipt directory (default): `.state/operator_receipts/`
- receipt actions include: `arm-live`, `disarm-live`, `flatten`, `submit-order-smoke`, `auto-disarm`

## Boundary statement

- This implementation does **not** attach to real broker execution.
- It does **not** claim production-ready operator runtime.
- It is a truthful bounded smoke/control surface to reduce fake-readiness risk for P1.

## Topology statement

- Runtime topology changed: no
- Scheduler topology changed: no
- CLI operator-control behavior changed: yes (seed executable posture + receipt trail)
