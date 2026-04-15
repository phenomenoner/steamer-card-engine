from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_WRAPPER = REPO_ROOT / "tools" / "steamer_card_engine_trading_day_preflight_cron.py"
DEFAULT_FIXTURE = "examples/probes/session_health.connected.json"


def main() -> int:
    env = dict(os.environ)
    env.setdefault("STEAMER_CARD_ENGINE_PROBE_JSON", DEFAULT_FIXTURE)
    result = subprocess.run(
        [sys.executable, str(CANONICAL_WRAPPER)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
