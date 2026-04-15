from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "ops" / "scripts" / "trading_day_preflight_seed.sh"
DEFAULT_DECK = "examples/decks/tw_cash_intraday.toml"
DEFAULT_AUTH_PROFILE = "examples/profiles/tw_cash_password_auth.toml"
DEFAULT_TRADING_DAY_STATUS = "open"


def main() -> int:
    probe_json = os.environ.get("STEAMER_CARD_ENGINE_PROBE_JSON", "")
    state_root = os.environ.get(
        "STEAMER_CARD_ENGINE_STATE_ROOT",
        "/root/.openclaw/workspace/.state/steamer-card-engine",
    )

    env = dict(os.environ)
    env["STEAMER_CARD_ENGINE_STATE_ROOT"] = state_root

    command = [
        str(RUNNER),
        DEFAULT_DECK,
        DEFAULT_AUTH_PROFILE,
        DEFAULT_TRADING_DAY_STATUS,
        probe_json,
    ]

    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as error:
        if result.returncode != 0:
            lines = [line for line in stderr.splitlines() if line][:3]
            detail = " | ".join(lines) if lines else "no-stderr"
            print(f"BLOCKED preflight_cron exitCode={result.returncode} stderr={detail}")
            return 0
        snippet = stdout.splitlines()[0] if stdout else "<empty>"
        print(f"BLOCKED preflight_cron invalid_json error={error.msg} stdout={snippet}")
        return 0

    if payload.get("preflight_status") == "ready":
        print("NO_REPLY")
        return 0

    blockers = payload.get("blockers") or []
    codes = ",".join(item.get("code", "unknown") for item in blockers[:4]) or "unknown"
    probe_source = (
        payload.get("logical_session", {})
        .get("boundary", {})
        .get("probe_source", "seed")
    )
    gate = payload.get("logical_session", {}).get("trading_day_gate", {}).get("status", "unknown")
    print(
        "BLOCKED preflight_status="
        f"{payload.get('preflight_status', 'unknown')} gate={gate} probe_source={probe_source} blockers={codes}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
