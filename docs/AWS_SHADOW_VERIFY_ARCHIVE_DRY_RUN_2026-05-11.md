# AWS shadow comparison verify/archive dry-run plan — 2026-05-11

## Verdict

Dry-run integration plan only. Do not modify live cron yet.

The AWS shadow comparison lane should remain a consumer of the existing AWS sim lifecycle:

```text
08:25 existing EC2 power-on/readiness
08:35 existing online sim kickoff starts normal sim and, later, the shadow observer worker
08:45 existing verify+autoheal checks normal sim and shadow observer health marker
13:40 existing archive/upload includes normal sim artifacts plus _shadow_compare artifacts
13:46 existing stop guardrail remains sole EC2 stop owner
```

## No lifecycle ownership

Forbidden in the shadow integration diff:

```text
start-instances
stop-instances
steamer_ec2_power_on_daily.py
steamer_ec2_stop_guardrail_daily.py
```

## Shadow artifact root

Remote planned root:

```text
/opt/trading/current/data/sim/${DAY}/_shadow_compare/order_intent_v1
```

Required files:

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

## Verify dry-run contract

The 08:45 verify stage should eventually check only for observer artifact health, not start the worker itself.

Minimum checks:

```bash
SHADOW_ROOT="$REPO/data/sim/$DAY/_shadow_compare/order_intent_v1"
test -d "$SHADOW_ROOT"
test -f "$SHADOW_ROOT/scenario_spec.json"
test -f "$SHADOW_ROOT/intent_compare_summary.json"
python3 - <<'PY'
import json, os
summary = json.load(open(os.environ['SHADOW_ROOT'] + '/intent_compare_summary.json'))
assert summary.get('observer_only') is True
assert summary.get('submits_orders') is False
assert summary.get('owns_ec2_lifecycle') is False
PY
```

If missing, classify as:

```text
shadow_observer_missing_artifact
shadow_observer_bad_summary
shadow_observer_contract_violation
```

## Archive dry-run contract

Current archive compresses the whole daily sim root:

```text
SRC="$REPO/data/sim/$DAY"
```

Because `_shadow_compare` lives under that root, no separate archive ownership is required. The dry-run proof is:

```bash
test -d "$REPO/data/sim/$DAY/_shadow_compare/order_intent_v1"
find "$REPO/data/sim/$DAY/_shadow_compare/order_intent_v1" -type f | sort
```

The generated archive manifest's `run_ids` may include `_shadow_compare`; that is acceptable as long as downstream landing treats it as artifact namespace, not strategy run id.

## Integration gate before live enable

Do not alter live kickoff/verify/archive until these pass locally:

```text
shadow_lane_preflight.py --dry-run-manifest ... => PASS_SHADOW_PREFLIGHT_DRY_RUN
aws_shadow_observer_dry_run.py emits all required artifacts
verify dry-run checks pass against emitted artifacts
archive inclusion dry-run lists shadow files under daily sim root
full pytest suite passes
WAL + docs ingest + local commit
```

## Current topology impact

None. This file is a dry-run contract only.
