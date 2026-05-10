# AWS shadow lane preflight — 2026-05-10

## Verdict

Dry-run preflight tooling landed for the future AWS shadow comparison lane.

```text
verdict: PASS_SHADOW_PREFLIGHT_DRY_RUN
```

No AWS cron, EC2 lifecycle, gateway, broker, or remote state was changed.

## Implementation

```text
tools/shadow_lane_preflight.py
tests/test_shadow_lane_preflight.py
```

Dry-run observer manifest:

```text
docs/AWS_SHADOW_OBSERVER_MANIFEST_DRY_RUN_2026-05-10.json
```

Preflight artifacts:

```text
runs/shadow-comparison/2026-05-10-preflight/shadow_lane_preflight_summary.json
runs/shadow-comparison/2026-05-10-preflight/shadow_lane_preflight_report.md
runs/shadow-comparison/2026-05-10-preflight-with-manifest/shadow_lane_preflight_summary.json
runs/shadow-comparison/2026-05-10-preflight-with-manifest/shadow_lane_preflight_report.md
```

## Live lifecycle roles observed

```text
archive_upload:        32bf7bac-be39-443d-bf7d-30d2fb496b50
ec2_power_on:          5137f344-041a-48be-933e-edd7ce34607f
ec2_stop_guardrail:    c2eeb4f3-6a84-4910-ac7a-25938dda18da
sim_kickoff:           e7ee7135-1378-40bf-a5c6-e23aa8757648
sim_verify_autoheal:   337bf8c5-bde8-4ab8-af54-36cbba4c5dbd
```

## Rules enforced by preflight

```text
shadow_lane_must_not_start_or_stop_ec2: true
shadow_lane_should_launch_under_existing_kickoff: true
shadow_lane_should_archive_under_existing_archive_job: true
```

The script supports an optional `--dry-run-manifest`; if that manifest contains lifecycle ownership tokens such as `start-instances`, `stop-instances`, `steamer_ec2_power_on_daily.py`, or `steamer_ec2_stop_guardrail_daily.py`, the preflight fails.

The current dry-run manifest also passed:

```text
verdict: PASS_SHADOW_PREFLIGHT_DRY_RUN
manifest_forbidden_lifecycle_hits: []
shadow_artifact_root: /opt/trading/current/data/sim/${DAY}/_shadow_compare/order_intent_v1
```

## Interpretation

This gives us a concrete guardrail for CK's requirement: use the same AWS machine/schedule, but do not accidentally double-start or double-stop the instance.

The next AWS-side implementation slice should be an EC2-side observer worker manifest that passes this preflight before any cron/kickoff integration.

## Tests

```text
uv run pytest tests/test_shadow_lane_preflight.py tests/test_order_intent_compare.py tests/test_triangle_compare.py tests/test_legacy_replay.py tests/test_legacy_lineage_and_tick_probe.py tests/test_legacy_equivalence.py tests/test_sim_compare.py -q
```

Observed:

```text
34 passed
```

## Topology/config impact

Unchanged. Preflight read-only inspected cron and wrote local artifacts only.
