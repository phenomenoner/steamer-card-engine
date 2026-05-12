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
    proc = subprocess.run(["aws", *args, "--region", region], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, check=False)
    if check and proc.returncode != 0:
        raise RuntimeError("aws command failed: " + " ".join(["aws", *args, "--region", region]) + "\nSTDOUT:\n" + proc.stdout + "\nSTDERR:\n" + proc.stderr)
    return proc


def build_remote_script(*, day_iso: str, remote_repo: str, output_dir: str) -> str:
    return rf'''#!/usr/bin/env bash
set -euo pipefail
umask 077
DAY={day_iso!r}
REPO={remote_repo!r}
OUT={output_dir!r}
mkdir -p "$OUT"
python3 - <<'PY'
import json, pathlib, sys
repo=pathlib.Path({remote_repo!r})
sys.path[:0]=[str(repo), str(repo/'src')]
try:
    import steamer_card_engine
    module_exists=True
    module_file=getattr(steamer_card_engine, '__file__', '')
except Exception as exc:
    module_exists=False
    module_file='IMPORT_ERROR: '+repr(exc)
checks={{
  'current_realpath': str(repo.resolve()),
  'module_exists': module_exists,
  'steamer_card_engine_file': module_file,
  'tool_exists': (repo/'tools/aws_shadow_observer_dry_run.py').exists(),
  'manifest_exists': (repo/'docs/AWS_SHADOW_OBSERVER_MANIFEST_DRY_RUN_2026-05-10.json').exists(),
  'disabled_env': (repo/'SHADOW_PAYLOAD_DISABLED.env').read_text().splitlines() if (repo/'SHADOW_PAYLOAD_DISABLED.env').exists() else [],
}}
checks['observer_only'] = 'STEAMER_SHADOW_OBSERVER_ONLY=1' in checks['disabled_env']
checks['submits_orders'] = not ('STEAMER_SHADOW_SUBMITS_ORDERS=0' in checks['disabled_env'])
checks['comparison_enabled'] = 'STEAMER_SHADOW_COMPARISON_ENABLED=1' in checks['disabled_env']
print(json.dumps({{'readiness': checks}}, sort_keys=True))
missing=[k for k in ['module_exists','tool_exists','manifest_exists','observer_only'] if not checks.get(k)]
if missing or checks['submits_orders'] or checks['comparison_enabled']:
    pathlib.Path({output_dir!r}, 'preopen_gate_receipt.json').write_text(json.dumps({{'schema':'steamer-shadow-preopen-gate/v1','day':{day_iso!r},'verdict':'BLOCKED_SHADOW_RUNTIME_NOT_READY','missing_or_bad':missing,'checks':checks}}, indent=2, sort_keys=True)+'\n')
    raise SystemExit(0)
PY
PYTHONPATH="$REPO:$REPO/src" timeout 180 python3 "$REPO/tools/aws_shadow_observer_dry_run.py" --day "$DAY" --output-dir "$OUT" --run-goal "preopen observer-only readiness dry-run; no broker orders"
python3 - <<'PY'
import json, pathlib
out=pathlib.Path({output_dir!r})
summary=json.loads((out/'intent_compare_summary.json').read_text())
receipt={{
  'schema':'steamer-shadow-preopen-gate/v1',
  'day':{day_iso!r},
  'verdict':'PASS_SHADOW_PREOPEN_GATE' if summary.get('observer_only') and not summary.get('submits_orders') and not summary.get('owns_ec2_lifecycle') else 'BLOCKED_SHADOW_SAFETY_FLAGS_BAD',
  'artifact_root':str(out),
  'observer_only':summary.get('observer_only'),
  'submits_orders':summary.get('submits_orders'),
  'owns_ec2_lifecycle':summary.get('owns_ec2_lifecycle'),
  'active_universe_count':summary.get('active_universe_count'),
  'legacy_intent_count':summary.get('legacy_intent_count'),
  'card_shadow_intent_count':summary.get('card_shadow_intent_count'),
  'intent_diff_count':summary.get('intent_diff_count'),
}}
(out/'preopen_gate_receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
print(json.dumps(receipt, sort_keys=True))
PY
'''


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only/observer-only Steamer AWS shadow pre-open gate via SSM.")
    parser.add_argument("--day", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--instance-id", default=DEFAULT_INSTANCE_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    parser.add_argument("--remote-output-dir")
    parser.add_argument("--wait-seconds", type=int, default=300)
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()
    day_compact = args.day.replace('-', '')
    remote_output_dir = args.remote_output_dir or f"{args.remote_repo}/data/sim/{day_compact}/_shadow_compare/preopen_gate_{stamp}"
    remote_script = build_remote_script(day_iso=args.day, remote_repo=args.remote_repo, output_dir=remote_output_dir)
    (out_dir / "remote_preopen_gate.sh").write_text(remote_script, encoding="utf-8")
    b64 = base64.b64encode(remote_script.encode()).decode()
    params = {"commands": [
        f"cat >/tmp/steamer_shadow_preopen_gate.b64 <<'B64'\n{b64}\nB64",
        "base64 -d /tmp/steamer_shadow_preopen_gate.b64 >/tmp/steamer_shadow_preopen_gate.sh",
        "bash /tmp/steamer_shadow_preopen_gate.sh",
    ], "executionTimeout": ["360"]}
    (out_dir / "ssm_params.json").write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    send = run_aws(["ssm", "send-command", "--instance-ids", args.instance_id, "--document-name", "AWS-RunShellScript", "--comment", f"steamer-shadow-preopen-gate-{args.day}-{stamp}", "--parameters", json.dumps(params)], profile=args.profile, region=args.region)
    (out_dir / "ssm_send.json").write_text(send.stdout, encoding="utf-8")
    command_id = json.loads(send.stdout)["Command"]["CommandId"]
    (out_dir / "ssm_command_id.txt").write_text(command_id + "\n", encoding="utf-8")

    invocation = None
    deadline = time.time() + args.wait_seconds
    while time.time() < deadline:
        proc = run_aws(["ssm", "get-command-invocation", "--command-id", command_id, "--instance-id", args.instance_id], profile=args.profile, region=args.region, check=False)
        if proc.returncode == 0:
            invocation = json.loads(proc.stdout)
            if invocation.get("Status") not in {"Pending", "InProgress", "Delayed"}:
                break
        time.sleep(5)
    if invocation is None:
        print(json.dumps({"schema":"steamer-shadow-preopen-gate/local-report/v1","day":args.day,"status":"BLOCKED_NO_INVOCATION","command_id":command_id}, sort_keys=True))
        return 2
    (out_dir / "ssm_invocation.json").write_text(json.dumps(invocation, indent=2) + "\n", encoding="utf-8")
    stdout = str(invocation.get("StandardOutputContent", ""))
    stderr = str(invocation.get("StandardErrorContent", ""))
    remote_receipt = None
    for line in reversed([x for x in stdout.splitlines() if x.strip().startswith('{')]):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get('schema') == 'steamer-shadow-preopen-gate/v1':
            remote_receipt = obj
            break
    report = {
        "schema": "steamer-shadow-preopen-gate/local-report/v1",
        "day": args.day,
        "status": invocation.get("Status"),
        "response_code": invocation.get("ResponseCode"),
        "command_id": command_id,
        "remote_artifact_root": remote_output_dir,
        "remote_receipt": remote_receipt,
        "stdout_tail": stdout[-3000:],
        "stderr_tail": stderr[-2000:],
    }
    (out_dir / "preopen_gate_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    if invocation.get("Status") != "Success":
        return 2
    return 0 if (remote_receipt or {}).get("verdict") == "PASS_SHADOW_PREOPEN_GATE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
