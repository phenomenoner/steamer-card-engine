# AWS shadow comparison lane plan — 2026-05-10

## Goal

Run a daily shadow comparison lane on the same AWS machine/lifecycle as the existing Steamer online sim, without creating duplicate EC2 start/stop ownership.

The lane must answer a specific test question each run:

```text
Did legacy and steamer-card-engine produce the same order intent under the same market stream and runtime snapshots?
```

## Existing AWS daily sim lifecycle observed

Current OpenClaw cron specs indicate these enabled trading-day jobs:

```text
08:25 Asia/Taipei  steamer: EC2 power-on + readiness
  jobId: 5137f344-041a-48be-933e-edd7ce34607f
  command: steamer_ec2_power_on_daily.py

08:35 Asia/Taipei  steamer: online sim kickoff (EC2)
  jobId: e7ee7135-1378-40bf-a5c6-e23aa8757648
  command: steamer_ec2_kickoff_daily.py

08:45 Asia/Taipei  steamer: online sim verify+autoheal (EC2)
  jobId: 337bf8c5-bde8-4ab8-af54-36cbba4c5dbd
  command: steamer_ec2_autoheal_verify_daily.py

13:40 Asia/Taipei  steamer: EC2 archive/upload runtime artifacts
  jobId: 32bf7bac-be39-443d-bf7d-30d2fb496b50
  command: steamer_ec2_archive_and_upload_daily.py

13:46 Asia/Taipei  steamer: EC2 stop guardrail
  live jobId: c2eeb4f3-6a84-4910-ac7a-25938dda18da
  command: steamer_ec2_stop_guardrail_daily.py
```

Note: an older local spec also referenced `0e831eea-ceff-42c6-b904-740b76dc3745`, but `openclaw cron list` did **not** show that second stop guardrail as currently live. Treat `c2eeb4f3-6a84-4910-ac7a-25938dda18da` as the live stop owner unless a later cron readback says otherwise.

Important schedule constraint:

- New shadow comparison must **not** own EC2 start/stop.
- Do not add another `start-instances` or `stop-instances` cron.
- Avoid a narrow 13:40-13:46 post-close compute window for anything heavy; archive and stop guardrail already live there.

## Recommended topology

### v1: EC2-side observer worker launched by existing kickoff

Attach the shadow lane as a child process or service started by the existing 08:35 kickoff on the already-started machine.

```text
08:25 OpenClaw starts/readies EC2
08:35 existing kickoff starts legacy/live-sim runtime
08:35+ same kickoff also starts shadow comparison observer in no-order mode
08:45 existing verify confirms both legacy runtime and shadow observer health
13:40 existing archive uploads both normal sim artifacts and shadow artifacts
13:46 existing stop guardrail remains the only stop owner
```

This prevents duplicate lifecycle ownership.

### v1 artifact contract

Each shadow run must emit:

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

### v1 run goals

Start with one narrow target per run:

```text
run_goal: REV_SHORT_AFTER_UP entry order intent only
must_match:
  - action
  - symbol
  - side
  - quantity
  - price_basis
  - order_type
  - time_in_force
classify_only:
  - reason wording
  - non-entry gate blocks
excluded_initially:
  - exit/trailing stop parity
  - actual broker fill parity
  - multi-account capital contention
```

## Conflict avoidance rules

1. No shadow cron may call EC2 power-on/stop.
2. If a cron is added later, it should be a **health/check/report** cron only, not lifecycle.
3. Any same-machine shadow worker must be launched by the existing kickoff or EC2-side supervisor.
4. Archive/upload must include shadow artifacts, but not replace existing artifacts.
5. Stop guardrail remains canonical. If duplicate stop jobs are confirmed active, resolve existing duplicate before adding shadow work.

## Dry-run before enable

Before enabling any AWS-side shadow worker:

```text
1. Local replay smoke: PASS_ENTER_INTENT on at least two historical days with actual orders.
2. EC2 dry-run command prints planned paths and exits without starting worker.
3. Archive dry-run confirms shadow artifact paths would be included.
4. Verify dry-run confirms expected health marker names.
5. No new start/stop command appears in the diff.
```

## Open questions / next implementation slice

- Identify the exact EC2 runtime artifact root used by `steamer_ec2_archive_and_upload_daily.py`.
- Add a shadow-worker launch manifest to kickoff script only after dry-run proof.

## Current topology impact

Plan only. No AWS cron/job/runtime changed in this slice.
