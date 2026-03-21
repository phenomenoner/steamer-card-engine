# 2026-03-15 — Steamer Card Engine M1 sprint live provisioning receipt

## Why this exists

The sprint pack was already arranged as repo truth.
This note receipts the move from **scaffold-only** to **partially live controller posture**.

## What was provisioned

One live cron job was created for the Steamer Card Engine M1 sprint controller:

1. `f4ab2bcc-eb96-4463-8398-ca67b4dc0437`
   - label: `controller: steamer-card-engine M1 sprint (progress, silent-on-green)`
   - schedule: `40 13 * * *` (`Asia/Taipei`)
   - role: midday progress / scorecard pass

Shared live posture for this pass:
- `agentId=cron-lite`
- `sessionTarget=isolated`
- `wakeMode=next-heartbeat`
- model override: `openai-codex/gpt-5.2`
- thinking: `high`
- timeout: `1800s`
- announce delivery to CK Telegram with `bestEffort=true`
- expected green-path output: `NO_REPLY`

## What remains scaffold-only

The second controller pass is intentionally **not** live yet:

- `f111abe4-845d-4b70-9dbb-c2130d8e261f`
  - label: `controller: steamer-card-engine M1 sprint (captain-prep, silent-on-green)`
  - posture: scaffolded / disabled

Reason:
- get milestone progress moving immediately
- keep runtime surface narrow while the first controller pass proves itself
- avoid turning on both passes before one clean observation cycle exists

## Sprint posture after provisioning

- M1 remains **sim-only** and **contract-first**.
- Replay proof remains frozen.
- The next active gate remains **live-sim-attached**.
- This live controller enablement does **not** widen runtime authority into live trading or broker submission semantics.

## Source-of-truth updates

- live job spec:
  - `cron/jobs/f4ab2bcc-eb96-4463-8398-ca67b4dc0437.md`
- scaffolded second pass:
  - `cron/jobs/f111abe4-845d-4b70-9dbb-c2130d8e261f.md`
- canonical sprint doc:
  - `/root/.openclaw/workspace/steamer-card-engine/ops/sprints/steamer-card-engine-m1-sim-comparability-sprint.md`
- activation pack:
  - `/root/.openclaw/workspace/steamer-card-engine/docs/tech-notes/2026-03-15_steamer_card_engine_m1_sprint-activation-pack.md`

## Rollback

If the live controller proves noisy, fake-busy, or drifty:
1. disable live job `f4ab2bcc-eb96-4463-8398-ca67b4dc0437`
2. leave the sprint doc as the historical record
3. keep `captain-prep` disabled
4. tighten the sprint pack/job spec before re-enabling

## Live receipts

- pre-change cron-store backup:
  - `/root/.openclaw/cron/jobs.json.bak.steamer-m1-progress-live-20260315T091310Z`
- live job creation result:
  - `openclaw cron add ...` created `f4ab2bcc-eb96-4463-8398-ca67b4dc0437`
- scheduler truth now includes the progress-pass live job; repo truth has been updated to match

## Topology statement

- **Control-plane truth changed**: Steamer M1 now has one live controller pass.
- **Boundary/capability truth unchanged**: still sim-only; no broker/live-trading authority expansion.
