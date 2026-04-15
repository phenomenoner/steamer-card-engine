#!/usr/bin/env bash
set -eu

DECK="${1:-examples/decks/tw_cash_intraday.toml}"
AUTH_PROFILE="${2:-examples/profiles/tw_cash_password_auth.toml}"
TRADING_DAY_STATUS="${3:-open}"
PROBE_JSON="${4:-}"
STATE_ROOT="${STEAMER_CARD_ENGINE_STATE_ROOT:-/root/.openclaw/workspace/.state/steamer-card-engine}"
PROBE_OUT="${STATE_ROOT}/session_probe.json"

mkdir -p "${STATE_ROOT}"

probe_args=(
  operator probe-session
  --auth-profile "${AUTH_PROFILE}"
  --trading-day-status "${TRADING_DAY_STATUS}"
  --output "${PROBE_OUT}"
  --json
)

if [ -n "${PROBE_JSON}" ]; then
  probe_args+=(--probe-json "${PROBE_JSON}")
fi

uv run steamer-card-engine "${probe_args[@]}" >/dev/null

uv run steamer-card-engine operator preflight-smoke \
  --deck "${DECK}" \
  --auth-profile "${AUTH_PROFILE}" \
  --trading-day-status "${TRADING_DAY_STATUS}" \
  --probe-json "${PROBE_OUT}" \
  --json
