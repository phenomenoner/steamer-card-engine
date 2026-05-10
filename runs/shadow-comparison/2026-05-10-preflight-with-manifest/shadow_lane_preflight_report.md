# AWS shadow lane preflight

## Verdict
PASS_SHADOW_PREFLIGHT_DRY_RUN

## Blockers
[]

## Live lifecycle roles
- ec2_power_on: `['5137f344-041a-48be-933e-edd7ce34607f']`
- sim_kickoff: `['e7ee7135-1378-40bf-a5c6-e23aa8757648']`
- sim_verify_autoheal: `['337bf8c5-bde8-4ab8-af54-36cbba4c5dbd']`
- archive_upload: `['32bf7bac-be39-443d-bf7d-30d2fb496b50']`
- ec2_stop_guardrail: `['c2eeb4f3-6a84-4910-ac7a-25938dda18da']`

## Rules
- Shadow lane must not start or stop EC2.
- Shadow lane should be launched by existing kickoff after EC2 readiness.
- Shadow lane artifacts should be archived by existing archive/upload job.

## Recommended next step
Add an EC2-side observer worker manifest only after this preflight passes and the manifest contains no start/stop lifecycle ownership.
