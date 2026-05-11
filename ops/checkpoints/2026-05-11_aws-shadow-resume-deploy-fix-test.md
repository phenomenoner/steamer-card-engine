# AWS shadow resume deploy/fix/test checkpoint — 2026-05-11 09:20 TPE

## Verdict

`SHADOW_OBSERVER_REMOTE_RUNTIME_READY_AND_SIM_RUNNING`

## What changed

- Deployed disabled-by-default observer runtime payload into `/opt/trading/current` from staged payload `/opt/trading/shadow_payloads/20260511T0054Z-shadow-observer-disabled/steamer-card-engine`.
- Added durable local runner `tools/aws_shadow_postclose_collect.py`.
- Added one-shot OpenClaw post-close collect job `8400d7fd-5a48-4948-adc6-d0b567fb5d42` for 2026-05-11 13:35 TPE.

## Safety invariants

- No broker order API calls.
- No EC2 start/stop ownership changes.
- No existing lifecycle cron owner changes.
- `/opt/trading/current` symlink target unchanged.
- Runtime payload defaults remain disabled: `STEAMER_SHADOW_COMPARISON_ENABLED=0`.
- Observer-only guards: `STEAMER_SHADOW_OBSERVER_ONLY=1`, `STEAMER_SHADOW_SUBMITS_ORDERS=0`.

## Verification receipts

- Deploy SSM: `runs/shadow-comparison/2026-05-11-resume-deploy-20260511T011329Z/ssm_deploy_current_invocation.json`.
- Remote readiness/dry-run: `runs/shadow-comparison/2026-05-11-resume-deploy-20260511T011329Z/ssm_readiness_dryrun_invocation.json`.
- Local pytest: `runs/shadow-comparison/2026-05-11-resume-deploy-20260511T011329Z/local_pytest_shadow.txt` (`4 passed`).
- Kickoff manual deterministic run: stdout `NO_REPLY`, exit 0.
- Verify/autoheal manual deterministic run: stdout `NO_REPLY`, exit 0.
- Immediate collect report: `runs/shadow-comparison/2026-05-11-resume-deploy-20260511T011329Z/immediate_shadow_collect/postclose_collect_report.json`.
- Cron topology check: `runs/shadow-comparison/2026-05-11-resume-deploy-20260511T011329Z/topology_and_stale_rule_check.txt`.

## Remaining gate

Post-close one-shot collect at 13:35 TPE should produce the final same-day receipt after more intraday data accumulates. It is still observer-only and should report blockers truthfully if source files are absent.
