# 2026-03-19 — steamer-card-engine P1 stage-1: capability posture contract (sim-only → live-capable)

Goal of this note: make the **capability posture ladder** explicit and operator-inspectable, without implying broad production readiness or unrestricted live authority.

Scope boundary:
- this is **Product Sprint P1** truth only (guarded live-capability posture)
- it must not steal Sprint A ownership
- it does not claim operator execution is already implemented (operator surfaces are still placeholder per `steamer-card-engine/docs/CLI_SPEC.md`)

## Terms: capability vs posture

- **Capability** = what the current auth/session + adapter stack is *permitted and able* to do (e.g. `trade_enabled`, `account_query_enabled`).
- **Posture** = what the runtime is *currently allowed to do* under operator governance (e.g. disarmed vs armed-live), even if capability exists.

Hard invariant:
- `trade_enabled=true` must never be treated as “live trading is happening”.
- `trade_enabled` and `armed_live` are distinct, and both must be inspectable.

## Capability posture ladder (contract target)

1) **SIM-ONLY / replay-sim**
   - intent/risk/execution receipts exist, but **no live market attachment** is required.
   - capability posture: `marketdata_enabled=false`, `trade_enabled=false`.

2) **LIVE-SIM / marketdata-attached, no live orders**
   - live market data may be enabled.
   - explicit invariant: **no broker order submission**.
   - capability posture commonly: `marketdata_enabled=true`, `trade_enabled=false` (preferred), `account_query_enabled` may be true/false depending on vendor.

3) **LIVE-CAPABLE (disarmed)**
   - credentials/session may permit trading (`trade_enabled=true`), but the runtime remains **disarmed**.
   - explicit invariant: **no order submission until operator arms**.

4) **ARMED-LIVE (operator-governed)**
   - operator explicitly arms live for a bounded scope (deck/account/time window).
   - runtime may submit broker orders, still under guardrails (flatten/emergency stop, forced exit windows, final-auction policy).

5) **FLATTEN / EMERGENCY posture (operator-triggered)**
   - a bounded operator control path exists to flatten/exit according to policy.
   - this is not a “strategy mode”; it is a safety posture.

## Operator-inspectable surfaces (minimum)

The docs already define the needed visibility contract:
- `steamer-card-engine/docs/AUTH_AND_SESSION_MODEL.md` defines `SessionContext` fields including `trade_enabled`.
- `steamer-card-engine/docs/CLI_SPEC.md` defines `auth inspect-session --json` and the operator command family.

Stage-1 contract requirement for P1:
- there must be **one place** an operator can read and unambiguously map:
  - current execution mode (`replay-sim` / `live-sim` / `live`)
  - session capabilities (`marketdata_enabled`, `trade_enabled`, `account_query_enabled`)
  - runtime posture (`armed_live` yes/no)

## What this does NOT claim

- It does not claim operator live execution is implemented today.
- It does not claim production readiness.
- It does not widen the product scope beyond the bounded ladder above.
