# AWS shadow comparison — Day 2 gate + summary setup

Date: 2026-05-11 TPE

## Goal
Prepare 2026-05-12 AWS shadow comparison continuation with:

1. preopen observer-only safety/readiness gate before the regular 08:35 kickoff;
2. stricter scripts-first kickoff cron wrapper to avoid agent wrapper drift;
3. postclose observer-only collect;
4. postclose human-readable summary derived from machine artifacts.

## Non-goals
- No broker order capability.
- No EC2 lifecycle ownership by shadow observer scripts.
- No change to `/opt/trading/current` symlink target in this setup slice.
- No gateway/runtime/model primary config changes.

## Installed / changed

### Existing recurring kickoff cron hardened
- job: `e7ee7135-1378-40bf-a5c6-e23aa8757648`
- change: payload now scripts-first with `toolsAllow=["exec"]`, `lightContext=true`, model `openai-codex/gpt-5.5`.
- command remains:
  `python3 /root/.openclaw/workspace/StrategyExecuter_Steamer-Antigravity/projects/steamer/tools/steamer_ec2_kickoff_daily.py`
- spec updated:
  `/root/.openclaw/workspace/openclaw-async-coding-playbook/cron/jobs/e7ee7135-1378-40bf-a5c6-e23aa8757648.md`

### New one-shot jobs for 2026-05-12

| Time TPE | Job | Job id | Purpose |
|---|---|---|---|
| 08:31 | AWS shadow comparison: preopen gate | `48cb6ada-1326-4b3c-801c-ebd4159abc00` | SSM observer-only readiness dry-run; silent on pass, blocked line on fail |
| 13:35 | AWS shadow comparison: postclose collect | `7b67ea43-ee57-4e3b-8034-42b233cbde6c` | Observer-only postclose artifact collection |
| 13:50 | AWS shadow comparison: day summary | `e55d94d0-eba7-4e87-a8f3-4ab34ea6e541` | Human-readable summary from postclose machine report |

Specs:
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/cron/jobs/48cb6ada-1326-4b3c-801c-ebd4159abc00.md`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/cron/jobs/7b67ea43-ee57-4e3b-8034-42b233cbde6c.md`
- `/root/.openclaw/workspace/openclaw-async-coding-playbook/cron/jobs/e55d94d0-eba7-4e87-a8f3-4ab34ea6e541.md`

## New local tools
- `tools/aws_shadow_preopen_gate.py`
- `tools/aws_shadow_day_summary.py`

Existing tool reused:
- `tools/aws_shadow_postclose_collect.py`

## Verifiers run

```text
cd /root/.openclaw/workspace/steamer-card-engine
python3 -m py_compile tools/aws_shadow_preopen_gate.py tools/aws_shadow_day_summary.py
python3 tools/aws_shadow_day_summary.py --day 2026-05-11 --out-dir runs/shadow-comparison/2026-05-11-day-summary-smoke
python3 tools/aws_shadow_day_summary.py --day 2099-01-01 --out-dir runs/shadow-comparison/2099-01-01-day-summary-counterfactual
```

Results:
- py_compile: pass
- Day 1 summary smoke: pass, wrote `runs/shadow-comparison/2026-05-11-day-summary-smoke/summary.md` and `summary.json`
- missing-report counterfactual: returns rc=2 and emits `BLOCKED aws-shadow-day-summary ...`, proving the summary path does not invent a status when collect is missing.

## Topology impact
Changed:
- existing kickoff cron payload hardened;
- three one-shot OpenClaw cron jobs added for 2026-05-12.

Unchanged:
- EC2 lifecycle cron owners remain power-on/kickoff/verify/archive/stop;
- broker auth/order paths unchanged;
- gateway config unchanged;
- `/opt/trading/current` symlink unchanged in this setup slice.

## Rollback
- Disable/remove one-shot jobs: `48cb6ada-1326-4b3c-801c-ebd4159abc00`, `7b67ea43-ee57-4e3b-8034-42b233cbde6c`, `e55d94d0-eba7-4e87-a8f3-4ab34ea6e541`.
- Revert kickoff cron payload to previous job spec if needed.
- Remove/ignore local helper scripts if the lane is retired.
