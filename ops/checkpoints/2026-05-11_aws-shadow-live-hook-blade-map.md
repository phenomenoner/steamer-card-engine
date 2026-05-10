# Blade map — AWS shadow comparison live hook — 2026-05-11

## Goal

Connect the AWS shadow comparison "takeoff" path so the existing AWS sim lifecycle can run an observer-only `steamer-card-engine` shadow comparison on the same EC2 machine, without adding EC2 lifecycle ownership or broker order submission.

## Non-goals

```text
- no EC2 start/stop cron changes
- no new lifecycle cron
- no live broker orders
- no real-money replacement claim
- no remote push/release
```

## Invariants

```text
08:25 power-on remains existing owner
08:35 kickoff remains existing launch owner
08:45 verify remains existing health-check owner
13:40 archive remains existing archive owner
13:46 stop guardrail remains existing stop owner
```

## Desired hook shape

```text
08:35 kickoff:
  if STEAMER_SHADOW_COMPARISON_ENABLED=1 and runtime exists:
    start observer-only shadow worker under $REPO/data/sim/$DAY/_shadow_compare/order_intent_v1
  else:
    no-op / marker receipt

08:45 verify:
  check shadow marker/summary only when enabled

13:40 archive:
  existing archive already captures $REPO/data/sim/$DAY, including _shadow_compare
```

## Expected artifacts

```text
scenario_spec.json
active_universe.json
broker_state_snapshots.jsonl
legacy_order_intents.jsonl
card_shadow_order_intents.jsonl
intent_diff.jsonl
intent_compare_summary.json
summary.md
```

## Verifier plan

```text
1. Inspect local kickoff/verify/archive seams.
2. Read-only inspect whether EC2 runtime has needed code/path, if EC2 is available.
3. If unavailable, produce blocker: deployment/runtime missing.
4. If available, add disabled-by-default hook and dry-run verifier.
5. Run local tests + shadow preflight.
6. Do not enable live mode until dry-run receipt and readback prove no lifecycle/order side effects.
```

## Rollback

```text
- revert hook commit
- ensure STEAMER_SHADOW_COMPARISON_ENABLED unset/0
- remove only shadow artifact subtree if explicitly requested
```

## Topology impact

TBD. This blade map is docs-only. Live hook enable would be topology-changing only if existing lifecycle scripts start invoking the observer.

## 2026-05-11 01:07 readiness finding

Live hook cannot be honestly declared connected yet because the EC2 instance is currently stopped:

```text
instance: i-037aa8c8a534e878f
state: stopped
```

This prevents read-only SSM verification of the remote runtime paths before changing the live 08:35/08:45/13:40 seams.

A one-shot readiness check has been scheduled after the existing 08:25 power-on and before 08:35 kickoff:

```text
jobId: 1d5c15ad-4d95-4b20-8ded-418bb1dd802d
at: 2026-05-11 08:30 Asia/Taipei
mode: read-only SSM/runtime inspection; no EC2 start/stop; no broker orders
```

If remote runtime is present, next safe move is observer-only hook enable under the existing lifecycle. If remote runtime is missing, blocker is deployment/runtime availability, not strategy parity.

## 2026-05-11 01:10 one-shot schedule hardening

Added one-shot follow-up jobs so the readiness/takeoff line does not depend on human memory:

```text
08:30 readiness readback
  jobId: 1d5c15ad-4d95-4b20-8ded-418bb1dd802d
  action: read-only remote runtime inspection after existing 08:25 power-on

08:33 takeoff execute/fail-safe
  jobId: 98a14a49-67d9-4c72-a748-100a768cbd38
  action: only connect observer-only takeoff if readiness proves preconditions; otherwise record blocker

08:50 post-kickoff receipt check
  jobId: 97a85311-b97c-47b3-ae05-f0d3fcd87762
  action: inspect readiness/takeoff/kickoff/verify receipts and report result
```

All one-shots are constrained:

```text
- no EC2 start/stop
- no broker orders
- no lifecycle cron mutation
- no real-money enablement
```
