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

## 2026-05-11 08:35 readiness result

Read-only SSM check succeeded against a running/Online EC2 instance, but takeoff is blocked: `/opt/trading/current` lacks `steamer_card_engine`, `tools/aws_shadow_observer_dry_run.py`, and the dry-run manifest. Local hook/manifest preflight remains green (`PASS_SHADOW_PREFLIGHT_DRY_RUN`, tests `2 passed`). Do not enable kickoff/verify seams yet; next same-risk action is a disabled-by-default observer-only payload deploy/readback, with no lifecycle cron mutation and no broker orders. Receipt: `/root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-takeoff-readiness-20260511T003906Z/takeoff_readiness_report.md`.


## 2026-05-11 08:58 staging/post-close orchestration update

Disabled observer-only payload has been staged on EC2 under:

```text
/opt/trading/shadow_payloads/20260511T0054Z-shadow-observer-disabled
```

Verifier receipts:

```text
local preflight: /root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-postclose-orchestration-20260511T005222Z/local_preflight/shadow_lane_preflight_summary.json
local tests: /root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-postclose-orchestration-20260511T005222Z/local_pytest_uv.log (4 passed)
S3/presign: /root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-postclose-orchestration-20260511T005222Z/s3_presign.json
remote stage SSM: /root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-postclose-orchestration-20260511T005222Z/ssm_stage_invocation.json
remote smoke: PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS
remote smoke root: /opt/trading/shadow_payloads/20260511T0054Z-shadow-observer-disabled/smoke/observer_artifacts
```

Safety readback:

```text
STEAMER_SHADOW_COMPARISON_ENABLED=0
STEAMER_SHADOW_OBSERVER_ONLY=1
STEAMER_SHADOW_SUBMITS_ORDERS=0
observer_only=true
submits_orders=false
owns_ec2_lifecycle=false
```

Today sim root preflight at ~08:56 TPE returned `MISSING_ROOT`, so collection is scheduled post-close rather than claiming current-day data exists now.

One-shot post-close jobs:

```text
13:35 TPE collect: 38079ba0-7727-4f75-b66e-58279c05fe7f
13:50 TPE readback: 366df94a-56f9-40c5-9463-6e0e6ca2cf26
```

Topology impact: only temporary one-shot OpenClaw jobs were added; existing EC2 lifecycle cron, live cron, broker auth/order paths, and `/opt/trading/current` symlink were not mutated.


S3 staging cleanup: source payload object was removed after successful remote SHA/readback; receipt: `/root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-postclose-orchestration-20260511T005222Z/s3_cleanup.log`.


## 2026-05-11 08:51 post-kickoff receipt check

Verdict: `SHADOW_OBSERVER_TAKEOFF_BLOCKED_FAIL_SAFE`.

- 08:30 readiness job `1d5c15ad-4d95-4b20-8ded-418bb1dd802d`: `BLOCKED_REMOTE_RUNTIME_MISSING_SHADOW_RELEASE`.
- 08:33 execute/fail-safe job `98a14a49-67d9-4c72-a748-100a768cbd38`: `NO_TAKEOFF_BLOCKED`; did not connect 08:35/08:45 observer seam.
- Existing 08:35 kickoff cron `e7ee7135-1378-40bf-a5c6-e23aa8757648`: cron history status `error`; no shadow observer seam had been connected.
- Existing 08:45 verify cron `337bf8c5-bde8-4ab8-af54-36cbba4c5dbd`: cron history status `ok`, summary `NO_REPLY`.
- Read-only SSM check confirmed `/opt/trading/current` still lacks shadow hook/manifest and no shadow artifact root exists for `2026-05-11`.
- Disabled staged payload exists at `/opt/trading/shadow_payloads/20260511T0054Z-shadow-observer-disabled`, but remains unwired and disabled-by-default.

Receipts:

```text
/root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-post-kickoff-receipt-check-20260511T010024Z/post_kickoff_receipt_check_report.md
/root/.openclaw/workspace/steamer-card-engine/runs/shadow-comparison/2026-05-11-post-kickoff-receipt-check-20260511T010024Z/post_kickoff_receipt_check_receipt.json
```

Side effects: no EC2 start/stop, no broker orders, no lifecycle/live cron mutation, no auth broadening.
