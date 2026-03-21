#!/usr/bin/env python3
"""Post-close watchdog for Steamer Card Engine M1 sprint controller.

Silent on green, one-line alert on actionable anomalies.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

TPE = ZoneInfo("Asia/Taipei")
JOB_ID = "f4ab2bcc-eb96-4463-8398-ca67b4dc0437"
RUNS_PATH = Path(f"/root/.openclaw/cron/runs/{JOB_ID}.jsonl")
STEAMER_ENGINE_REPO = Path("/root/.openclaw/workspace/steamer-card-engine")
MANIFEST_ROOT = STEAMER_ENGINE_REPO / "runs" / "steamer-card-engine"


def _now_tpe() -> dt.datetime:
    return dt.datetime.now(TPE)


def _today_finished_runs() -> list[dict]:
    today = _now_tpe().date()
    rows: list[dict] = []
    if not RUNS_PATH.exists():
        return rows
    for line in RUNS_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("action") != "finished":
            continue
        run_at_ms = rec.get("runAtMs")
        if not isinstance(run_at_ms, int):
            continue
        run_day = dt.datetime.fromtimestamp(run_at_ms / 1000, tz=TPE).date()
        if run_day == today:
            rows.append(rec)
    rows.sort(key=lambda r: int(r.get("runAtMs") or 0))
    return rows


def _live_sim_bundle_count() -> int:
    if not MANIFEST_ROOT.exists():
        return 0
    total = 0
    for path in MANIFEST_ROOT.rglob("run-manifest.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if payload.get("run_type") == "live-sim":
            total += 1
    return total


def _sim_run_live_supported() -> bool:
    cmd = [
        "uv",
        "run",
        "--project",
        str(STEAMER_ENGINE_REPO),
        "--",
        "steamer-card-engine",
        "sim",
        "--help",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip().splitlines()
        err = stderr[0] if stderr else f"returncode={proc.returncode}"
        print(f"STEAMER_M1_POSTCLOSE ALERT sim_help_failed job={JOB_ID} err={err}")
        raise SystemExit(0)
    return "run-live" in (proc.stdout or "")


def main() -> int:
    now = _now_tpe()
    # Trading-day only (Mon..Fri)
    if now.weekday() >= 5:
        print("NO_REPLY")
        return 0

    today_runs = _today_finished_runs()
    if not today_runs:
        print(
            "STEAMER_M1_POSTCLOSE ALERT "
            f"missing_progress_run date={now.date().isoformat()} job={JOB_ID} expected_schedule=13:40"
        )
        return 0

    latest = today_runs[-1]
    status = str(latest.get("status") or "unknown")
    run_at_ms = int(latest.get("runAtMs") or 0)
    run_at = dt.datetime.fromtimestamp(run_at_ms / 1000, tz=TPE).strftime("%H:%M:%S")
    if status != "ok":
        err = str(latest.get("error") or "unknown")
        print(
            "STEAMER_M1_POSTCLOSE ALERT "
            f"progress_run_not_ok status={status} run_at={run_at} job={JOB_ID} err={err[:140]}"
        )
        return 0

    live_sim_count = _live_sim_bundle_count()
    supports_run_live = _sim_run_live_supported()

    if live_sim_count == 0 and not supports_run_live:
        print(
            "STEAMER_M1_POSTCLOSE WARN "
            "stage4_blocked reason=sim-run-live-missing "
            f"live_sim_bundles={live_sim_count} "
            "next=implement-minimal-sim-run-live-skeleton"
        )
        return 0

    if live_sim_count == 0:
        print(
            "STEAMER_M1_POSTCLOSE WARN "
            "stage4_pending reason=no-live-sim-bundle "
            f"live_sim_bundles={live_sim_count} "
            "next=run-one-live-sim-dry-run"
        )
        return 0

    print("NO_REPLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
