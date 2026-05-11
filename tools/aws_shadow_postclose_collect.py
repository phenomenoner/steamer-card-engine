#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

DEFAULT_INSTANCE_ID = "i-037aa8c8a534e878f"
DEFAULT_REGION = "ap-east-2"
DEFAULT_PROFILE = "lyria-trading-ops"
DEFAULT_REMOTE_REPO = "/opt/trading/current"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_aws(args: list[str], *, profile: str, region: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = profile
    cmd = ["aws", *args, "--region", region]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError(
            "aws command failed: " + " ".join(cmd) + "\nSTDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr
        )
    return proc


def build_remote_script(*, day_iso: str, day_compact: str, remote_repo: str, artifact_root: str, run_goal: str) -> str:
    return rf'''#!/usr/bin/env bash
set -euo pipefail
umask 077
DAY_ISO={day_iso!r}
DAY_COMPACT={day_compact!r}
REPO={remote_repo!r}
ROOT="$REPO/data/sim/$DAY_COMPACT"
OUT={artifact_root!r}
mkdir -p "$OUT"
RECEIPT="$OUT/postclose_collect_remote_receipt.json"
if [ ! -d "$ROOT" ]; then
  cat > "$RECEIPT" <<JSON
{{"schema":"steamer-shadow-postclose-collect/v1","verdict":"BLOCKED_TODAY_SIM_ROOT_MISSING","day":"$DAY_ISO","sim_root":"$ROOT","artifact_root":"$OUT","observer_only":true,"submits_orders":false,"owns_ec2_lifecycle":false}}
JSON
  echo "BLOCKED_TODAY_SIM_ROOT_MISSING $ROOT"
  exit 0
fi
python3 - <<'PY'
import importlib, json, pathlib, sys
repo=pathlib.Path({remote_repo!r})
sys.path[:0]=[str(repo), str(repo/'src')]
import steamer_card_engine
checks={{
  'current_realpath': str(repo.resolve()),
  'steamer_card_engine_file': steamer_card_engine.__file__,
  'tool_exists': (repo/'tools/aws_shadow_observer_dry_run.py').exists(),
  'manifest_exists': (repo/'docs/AWS_SHADOW_OBSERVER_MANIFEST_DRY_RUN_2026-05-10.json').exists(),
  'disabled_env': (repo/'SHADOW_PAYLOAD_DISABLED.env').read_text().splitlines() if (repo/'SHADOW_PAYLOAD_DISABLED.env').exists() else [],
}}
assert checks['tool_exists'] and checks['manifest_exists']
assert 'STEAMER_SHADOW_COMPARISON_ENABLED=0' in checks['disabled_env']
assert 'STEAMER_SHADOW_OBSERVER_ONLY=1' in checks['disabled_env']
assert 'STEAMER_SHADOW_SUBMITS_ORDERS=0' in checks['disabled_env']
print(json.dumps({{'readiness': checks}}, sort_keys=True))
PY
find "$ROOT" -path '*/_shadow_compare/*' -prune -o -type f -print | sort > "$OUT/source_inventory.txt"
orders=$(find "$ROOT" -path '*/_shadow_compare/*' -prune -o -type f \( -name 'orders.jsonl' -o -name '*orders*.jsonl' \) -print 2>/dev/null | sort | head -1 || true)
legacy_decisions=$(find "$ROOT" -path '*/_shadow_compare/*' -prune -o -type f \( -name 'decisions.jsonl' -o -name '*decision*.jsonl' \) -print 2>/dev/null | sort | head -1 || true)
candidate_decisions=$(find "$ROOT" -path '*/_shadow_compare/*' -prune -o -type f \( -name '*candidate*decisions*.jsonl' -o -name '*card*decisions*.jsonl' -o -name '*decision_trace*.jsonl' -o -name 'card_shadow_decisions.jsonl' \) -print 2>/dev/null | sort | head -1 || true)
args=(--day "$DAY_ISO" --output-dir "$OUT" --run-goal {run_goal!r})
[ -n "$orders" ] && args+=(--legacy-orders "$orders")
[ -n "$legacy_decisions" ] && args+=(--legacy-decisions "$legacy_decisions")
[ -n "$candidate_decisions" ] && args+=(--candidate-decisions "$candidate_decisions")
PYTHONPATH="$REPO:$REPO/src" timeout 600 python3 "$REPO/tools/aws_shadow_observer_dry_run.py" "${{args[@]}}"
python3 - <<PY
import json, pathlib
out=pathlib.Path({artifact_root!r})
summary=json.loads((out/'intent_compare_summary.json').read_text())
required=['scenario_spec.json','active_universe.json','broker_state_snapshots.jsonl','legacy_order_intents.jsonl','card_shadow_order_intents.jsonl','intent_diff.jsonl','intent_compare_summary.json','summary.md','source_inventory.txt']
receipt={{
 'schema':'steamer-shadow-postclose-collect/v1',
 'verdict': summary.get('verdict'),
 'day':{day_iso!r},
 'sim_root': '$ROOT',
 'artifact_root': str(out),
 'required_artifacts_present': all((out/x).exists() for x in required),
 'observer_only': summary.get('observer_only'),
 'submits_orders': summary.get('submits_orders'),
 'owns_ec2_lifecycle': summary.get('owns_ec2_lifecycle'),
 'active_universe_count': summary.get('active_universe_count'),
 'legacy_intent_count': summary.get('legacy_intent_count'),
 'card_shadow_intent_count': summary.get('card_shadow_intent_count'),
 'intent_diff_count': summary.get('intent_diff_count'),
 'selected_inputs': {{'orders': '$orders', 'legacy_decisions': '$legacy_decisions', 'candidate_decisions': '$candidate_decisions'}},
}}
(out/'postclose_collect_remote_receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\\n')
print(json.dumps(receipt, sort_keys=True))
PY
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Run observer-only Steamer AWS shadow post-close collect via SSM.")
    parser.add_argument("--day", required=True, help="Trading day, YYYY-MM-DD")
    parser.add_argument("--out-dir", required=True, help="Local receipt directory")
    parser.add_argument("--instance-id", default=DEFAULT_INSTANCE_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    parser.add_argument("--remote-artifact-root")
    parser.add_argument("--run-goal", default="post-close observer-only shadow comparison; no broker orders")
    parser.add_argument("--wait-seconds", type=int, default=720)
    args = parser.parse_args()

    day_iso = args.day
    day_compact = day_iso.replace("-", "")
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    remote_artifact_root = args.remote_artifact_root or f"{args.remote_repo}/data/sim/{day_compact}/_shadow_compare/order_intent_v1_{stamp}"

    remote_script = build_remote_script(
        day_iso=day_iso,
        day_compact=day_compact,
        remote_repo=args.remote_repo,
        artifact_root=remote_artifact_root,
        run_goal=args.run_goal,
    )
    (out_dir / "remote_postclose_collect.sh").write_text(remote_script, encoding="utf-8")
    b64 = base64.b64encode(remote_script.encode()).decode()
    params = {"commands": [
        f"cat >/tmp/steamer_shadow_postclose_collect.b64 <<'B64'\n{b64}\nB64",
        "base64 -d /tmp/steamer_shadow_postclose_collect.b64 >/tmp/steamer_shadow_postclose_collect.sh",
        "bash /tmp/steamer_shadow_postclose_collect.sh",
    ]}
    (out_dir / "ssm_params.json").write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    send = run_aws([
        "ssm", "send-command",
        "--instance-ids", args.instance_id,
        "--document-name", "AWS-RunShellScript",
        "--comment", f"steamer-shadow-postclose-collect-{day_iso}-{stamp}",
        "--parameters", json.dumps(params),
    ], profile=args.profile, region=args.region)
    (out_dir / "ssm_send.json").write_text(send.stdout, encoding="utf-8")
    command_id = json.loads(send.stdout)["Command"]["CommandId"]
    (out_dir / "ssm_command_id.txt").write_text(command_id + "\n", encoding="utf-8")

    invocation: dict[str, object] | None = None
    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        proc = run_aws([
            "ssm", "get-command-invocation",
            "--command-id", command_id,
            "--instance-id", args.instance_id,
        ], profile=args.profile, region=args.region, check=False)
        if proc.returncode == 0:
            invocation = json.loads(proc.stdout)
            if invocation.get("Status") not in {"Pending", "InProgress", "Delayed"}:
                break
        time.sleep(5)

    if invocation is None:
        proc = run_aws([
            "ssm", "get-command-invocation",
            "--command-id", command_id,
            "--instance-id", args.instance_id,
        ], profile=args.profile, region=args.region, check=False)
        if proc.returncode == 0:
            invocation = json.loads(proc.stdout)

    if invocation:
        (out_dir / "ssm_invocation.json").write_text(json.dumps(invocation, indent=2) + "\n", encoding="utf-8")

    stdout = str((invocation or {}).get("StandardOutputContent", ""))
    stderr = str((invocation or {}).get("StandardErrorContent", ""))
    report = {
        "schema": "steamer-shadow-postclose-collect/local-report/v1",
        "day": day_iso,
        "instance_id": args.instance_id,
        "command_id": command_id,
        "status": (invocation or {}).get("Status", "UNKNOWN"),
        "response_code": (invocation or {}).get("ResponseCode"),
        "remote_artifact_root": remote_artifact_root,
        "stdout_tail": stdout[-4000:],
        "stderr_tail": stderr[-4000:],
    }
    (out_dir / "postclose_collect_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "Success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
