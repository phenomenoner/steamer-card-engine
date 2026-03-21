# 2026-03-19 — steamer-card-engine Product Sprint P1 / Live Trading Capability v0 sprint pack

## Framework-fit verdict

**Fit: yes.**

This is a bounded milestone sprint because:
- the product gate is legible
- the boundary can stay explicit and safety-first
- repo truth already exposes the product scope, auth/session model, day-trading guardrails, CLI surface, and migration plan
- the controller can stay a control-plane layer and does not need to become the main coding worker

## Milestone

Make **Live Trading Capability v0** operator-credible and reportable for `steamer-card-engine`.

Plain meaning:
- the product has an explicit guarded path from replay/live-sim productization into live-capability posture
- auth/session capability state is inspectable
- operator controls for arm/disarm/status/flatten are contractually clear
- the product line can move toward live capability without pretending broad autonomy or production readiness

Boundary note:
- this sprint is about **capability posture and operator-safe productization**, not about opening unrestricted live trading authority
- the milestone closes on a reportable contract pack and bounded product-readiness posture, not on mass live deployment

## Path-connectivity verdict + best-case timing

Connectivity verdict: **connected**.

Why it connects:
1. M1 already proved the product can carry sim-only replay/live-sim artifact contracts
2. product docs already freeze the key safety boundaries (`PRODUCT_SCOPE`, `DAYTRADING_GUARDRAILS`, `AUTH_AND_SESSION_MODEL`, `MIGRATION_PLAN`, `CLI_SPEC`)
3. the next honest bounded edge is guarded live-capability posture, not a giant rewrite

Best-case timing map:
- stage-1 capability-posture-contract: **0.5-1 good active day**
- stage-2 operator-control-contract: **0.5-1 good active day**
- stage-3 bounded-live-path-contract: **0.5-1 good active day**
- stage-4 reportable-p1: **0.5-1 good active day**
- fastest plausible finish: **~2-4 calendar days**

Launching user confirmation:
- CK explicitly approved opening this adjacent product line on 2026-03-19
- CK explicitly required that it coexist with Sprint A without fighting it

## Canonical sprint surfaces

- sprint doc:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-p1-live-trading-capability-v0-sprint.md`
- controller config:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprint-controllers/steamer-card-engine-p1-live-trading-capability-v0.controller.v1.yaml`
- scaffold cron specs:
  - `cron/jobs/6fc06cb3-caba-4567-a058-b568a6c94c67.md`
  - `cron/jobs/f2defcce-1a85-4d44-91a5-20def71a488c.md`

## Recommended stage order

1. `capability-posture-contract`
2. `operator-control-contract`
3. `bounded-live-path-contract`
4. `reportable-p1`

## Non-negotiable contract

1. operator-governed live authority remains explicit
2. auth/session posture must reveal whether trade permission exists
3. operator commands remain guarded and auditable
4. this sprint does not claim broad production readiness
5. this sprint does not own strategy/selection coupling; that remains Sprint A

## Immediate forcing move

Update (2026-03-20):
- stage-1 `capability-posture-contract` is closed.
- stage-2 `operator-control-contract` is closed.
- current forcing move: close **stage-3 bounded-live-path-contract** (one coherent bounded path from live-capable/disarmed into armed-live, with TTL + disarm/flatten exits and explicit capability/posture visibility).

## Topology statement

- repo truth changed: **yes**
- control-plane docs changed: **yes**
- live cron topology changed by this note alone: **no**
- runtime placement changed: **no**
- authority boundary changed: **no**
