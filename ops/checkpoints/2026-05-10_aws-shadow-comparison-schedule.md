# WAL — AWS shadow comparison schedule — 2026-05-10

## Change

Named the order-intent equivalence lane **AWS shadow comparison** and installed a daily intake/preflight cron.

## Why now

CK requested a distinct lane name and schedule: he may provide a stock-code batch before 09:00 Asia/Taipei; if none is provided, use the existing AWS sim watchlist/selection. CK also requested that future mentions of AWS shadow comparison retrieve/update the active goal.

## Cron

```text
jobId: 19b01d8b-94b6-446a-a89a-bf458a150c6a
name: AWS shadow comparison daily intake/preflight
schedule: 55 8 * * 1-5 @ Asia/Taipei
sessionTarget: current Telegram direct session
```

## Guardrails

```text
- observer/preflight only
- no EC2 start/stop lifecycle ownership
- no lifecycle cron changes
- no live broker orders
- use CK-provided stock-code batch if received before 09:00
- otherwise use existing AWS sim watchlist/selection
- update WAL/goal receipts when meaningful work happens
```

## Long-term memory

Stored durable memory: `AWS shadow comparison` names the active legacy-vs-card-engine order-intent equivalence goal; retrieving this term should also retrieve/update the goal.

## Topology impact

Cron topology changed: one new current-session agentTurn intake/preflight cron. No AWS, EC2, broker, gateway, or lifecycle cron changed.

## Rollback

Remove cron job `19b01d8b-94b6-446a-a89a-bf458a150c6a` and revert this WAL commit.
