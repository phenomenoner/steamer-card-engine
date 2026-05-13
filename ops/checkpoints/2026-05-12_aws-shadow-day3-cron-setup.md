# AWS shadow comparison — Day 3 cron setup

## Decision
Prepare 2026-05-13 AWS shadow comparison continuation with three observer-only one-shot jobs, alongside the already-enabled recurring AWS sim lifecycle and daily intake/preflight jobs.

## Why now
2026-05-12 completed as no-signal parity with observer-only safety flags intact. CK asked to continue testing tomorrow and verify the cron surface.

## Installed one-shot jobs

| Time Asia/Taipei | Job | Job ID | Purpose |
|---|---|---|---|
| 2026-05-13 08:31 | AWS shadow comparison: preopen gate | `cfe2da67-651c-4f51-ba28-b63d7dee3436` | Observer-only readiness dry-run before market path |
| 2026-05-13 13:35 | AWS shadow comparison: postclose collect | `4ca8051c-4748-495a-b523-cefed496143d` | Observer-only postclose artifact collection |
| 2026-05-13 13:50 | AWS shadow comparison: day summary | `87d927d8-dafc-4571-b05b-541c5c3a6eff` | Human-readable summary derived from machine artifacts |

## Existing recurring jobs verified

| Time Asia/Taipei | Job | Job ID |
|---|---|---|
| Weekdays 08:25 | steamer: EC2 power-on + readiness | `5137f344-041a-48be-933e-edd7ce34607f` |
| Weekdays 08:35 | steamer: online sim kickoff | `e7ee7135-1378-40bf-a5c6-e23aa8757648` |
| Weekdays 08:45 | steamer: online sim verify+autoheal | `337bf8c5-bde8-4ab8-af54-36cbba4c5dbd` |
| Weekdays 08:55 | AWS shadow comparison daily intake/preflight | `19b01d8b-94b6-446a-a89a-bf458a150c6a` |

## Safety / invariants
- Observer-only: no broker orders.
- No EC2 lifecycle ownership by the shadow jobs.
- Existing AWS lifecycle cron remains the owner of EC2 start/verify.
- One-shot jobs are `deleteAfterRun=true`.

## Verification
- `py_compile` passed for:
  - `tools/aws_shadow_preopen_gate.py`
  - `tools/aws_shadow_postclose_collect.py`
  - `tools/aws_shadow_day_summary.py`
- Cron readback showed all three Day 3 one-shots enabled with next runs:
  - 2026-05-13 08:31 Asia/Taipei
  - 2026-05-13 13:35 Asia/Taipei
  - 2026-05-13 13:50 Asia/Taipei
- Cron specs written under `openclaw-async-coding-playbook/cron/jobs/` for all three job IDs.

## Topology impact
Changed: added three one-shot cron jobs for 2026-05-13 AWS shadow comparison Day 3. No model routing, gateway config, EC2 lifecycle ownership, or broker-order authority changed.
