from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from steamer_card_engine.manifest import (
    ManifestValidationError,
    load_auth_profile,
    load_card_manifest,
    load_cards_from_dir,
    load_deck_manifest,
    load_global_config,
    summarize_auth_profile,
    summarize_card_manifest,
    summarize_deck_manifest,
    summarize_global_config,
)
from steamer_card_engine.operator_control import (
    operator_arm_live,
    operator_disarm_live,
    operator_flatten,
    operator_live_smoke_readiness,
    operator_status,
    operator_submit_order_smoke,
)
from steamer_card_engine.sim_compare import (
    SimCompareError,
    compare_bundles,
    normalize_baseline_bundle,
)
from steamer_card_engine.strategy_catalog import (
    StrategyCatalogValidationError,
    load_strategy_catalog,
    query_strategies_by_regime,
    summarize_strategy_catalog,
)


TPE = ZoneInfo("Asia/Taipei")
CRITICAL_SURFACES = ("marketdata", "broker")
STEAMER_CRON_HEALTH_ROOT = Path(
    os.environ.get(
        "STEAMER_CARD_ENGINE_STEAMER_CRON_ROOT",
        "/root/.openclaw/workspace/.state/steamer/cron-health",
    )
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steamer-card-engine",
        description="Card-oriented runtime seed for Taiwan stock intraday strategy operations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth = subparsers.add_parser("auth", help="Auth profile validation and inspection")
    auth_sub = auth.add_subparsers(dest="auth_command", required=True)

    auth_validate = auth_sub.add_parser(
        "validate-profile", help="Validate an auth profile manifest"
    )
    auth_validate.add_argument("path")

    auth_inspect = auth_sub.add_parser("inspect-profile", help="Inspect an auth profile manifest")
    auth_inspect.add_argument("path")
    auth_inspect.add_argument("--json", action="store_true", dest="as_json")

    auth_inspect_session = auth_sub.add_parser(
        "inspect-session",
        help="Inspect the logical session and capability posture for a chosen auth profile",
    )
    auth_inspect_session.add_argument("--auth-profile", required=True)
    auth_inspect_session.add_argument("--session-id")
    auth_inspect_session.add_argument(
        "--probe-json",
        help="Optional JSON snapshot overriding the seed session_status/health fields",
    )
    auth_inspect_session.add_argument(
        "--probe-source",
        choices=("seed", "steamer-cron-health"),
        help="Optional named probe source when no explicit --probe-json snapshot is supplied",
    )
    auth_inspect_session.add_argument(
        "--probe-date",
        help="Optional Asia/Taipei probe date (YYYYMMDD) for named probe sources",
    )
    auth_inspect_session.add_argument(
        "--trading-day-status",
        choices=("open", "closed", "unknown"),
        default="unknown",
    )
    auth_inspect_session.add_argument("--json", action="store_true", dest="as_json")

    author = subparsers.add_parser("author", help="Authoring and validation commands")
    author_sub = author.add_subparsers(dest="author_command", required=True)

    init_card = author_sub.add_parser("init-card", help="Scaffold a new card definition")
    init_card.add_argument("name")

    validate_card = author_sub.add_parser("validate-card", help="Validate a card manifest path")
    validate_card.add_argument("path")

    inspect_card = author_sub.add_parser("inspect-card", help="Inspect a card manifest")
    inspect_card.add_argument("path")
    inspect_card.add_argument("--json", action="store_true", dest="as_json")

    validate_deck = author_sub.add_parser("validate-deck", help="Validate a deck manifest path")
    validate_deck.add_argument("path")

    inspect_deck = author_sub.add_parser("inspect-deck", help="Inspect a deck manifest")
    inspect_deck.add_argument("path")
    inspect_deck.add_argument(
        "--cards-dir",
        default="examples/cards",
        help="Directory containing card TOML files for symbol/feature resolution",
    )
    inspect_deck.add_argument("--json", action="store_true", dest="as_json")

    validate_global = author_sub.add_parser(
        "validate-global", help="Validate an engine global config manifest path"
    )
    validate_global.add_argument("path")

    inspect_global = author_sub.add_parser("inspect-global", help="Inspect a global config manifest")
    inspect_global.add_argument("path")
    inspect_global.add_argument("--json", action="store_true", dest="as_json")

    catalog = subparsers.add_parser(
        "catalog",
        help="Discovery-only strategy catalog metadata commands (read-only)",
    )
    catalog_sub = catalog.add_subparsers(dest="catalog_command", required=True)

    catalog_validate = catalog_sub.add_parser("validate", help="Validate a strategy catalog metadata file")
    catalog_validate.add_argument("path")

    catalog_inspect = catalog_sub.add_parser("inspect", help="Inspect a strategy catalog metadata file")
    catalog_inspect.add_argument("path")
    catalog_inspect.add_argument("--json", action="store_true", dest="as_json")

    catalog_query = catalog_sub.add_parser(
        "query",
        help="Query which cards are relevant under one or more market regimes",
    )
    catalog_query.add_argument("path")
    catalog_query.add_argument(
        "--regime",
        action="append",
        required=True,
        dest="regimes",
        help="Market regime tag to match (repeatable)",
    )
    catalog_query.add_argument("--limit", type=int)
    catalog_query.add_argument("--json", action="store_true", dest="as_json")

    replay = subparsers.add_parser("replay", help="Replay and analysis commands")
    replay_sub = replay.add_subparsers(dest="replay_command", required=True)
    replay_run = replay_sub.add_parser("run", help="Run a replay job")
    replay_run.add_argument("--deck", required=True)
    replay_run.add_argument("--date", required=True)
    replay_run.add_argument("--scenario-id")
    replay_run.add_argument("--baseline-dir", required=True)
    replay_run.add_argument("--output-root", default="runs")
    replay_run.add_argument("--run-id")
    replay_run.add_argument("--scenario-spec")
    replay_run.add_argument("--max-events", type=int)
    replay_run.add_argument("--max-decisions", type=int)
    replay_run.add_argument("--fill-model", default="sim-fill-v1")
    replay_run.add_argument("--dry-run", action="store_true")
    replay_run.add_argument("--json", action="store_true", dest="as_json")

    sim = subparsers.add_parser("sim", help="SIM artifact normalization/comparison commands")
    sim_sub = sim.add_subparsers(dest="sim_command", required=True)

    normalize = sim_sub.add_parser(
        "normalize-baseline",
        help="Normalize legacy baseline artifacts into an M1-compatible SIM bundle",
    )
    normalize.add_argument("--baseline-dir", required=True)
    normalize.add_argument("--output-dir", required=True)
    normalize.add_argument("--session-date", required=True)
    normalize.add_argument("--scenario-id", required=True)
    normalize.add_argument("--run-id")
    normalize.add_argument("--lane", default="baseline-bot")
    normalize.add_argument("--scenario-spec")
    normalize.add_argument("--max-events", type=int)
    normalize.add_argument("--max-decisions", type=int)
    normalize.add_argument("--fill-model", default="sim-fill-v1")
    normalize.add_argument("--json", action="store_true", dest="as_json")

    run_live = sim_sub.add_parser(
        "run-live",
        help=(
            "Run a market-data-attached live-sim session (sim-only) and emit a v1 bundle. "
            "(M1 bridge implementation: consumes a captured baseline directory.)"
        ),
    )
    run_live.add_argument("--deck", required=True)
    run_live.add_argument("--session-date", required=True)
    run_live.add_argument("--scenario-id")
    run_live.add_argument(
        "--baseline-dir",
        required=True,
        help="Captured baseline directory containing ticks.jsonl + decisions.jsonl",
    )
    run_live.add_argument("--output-root", default="runs")
    run_live.add_argument("--run-id")
    run_live.add_argument("--scenario-spec")
    run_live.add_argument("--max-events", type=int)
    run_live.add_argument("--max-decisions", type=int)
    run_live.add_argument("--fill-model", default="sim-fill-v1")
    run_live.add_argument("--dry-run", action="store_true")
    run_live.add_argument("--json", action="store_true", dest="as_json")

    compare = sim_sub.add_parser(
        "compare",
        help="Compare two SIM bundles with M1 hard-stop checks",
    )
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--output-dir", required=True)
    compare.add_argument("--allow-missing-fingerprint", action="store_true")
    compare.add_argument("--json", action="store_true", dest="as_json")

    operator = subparsers.add_parser("operator", help="Operator governance commands")
    operator_sub = operator.add_subparsers(dest="operator_command", required=True)

    status = operator_sub.add_parser("status", help="Inspect runtime posture")
    status.add_argument("--auth-profile")
    status.add_argument("--session-id")
    status.add_argument("--state-file", default=".state/operator_posture.json")
    status.add_argument("--receipt-dir", default=".state/operator_receipts")
    status.add_argument("--json", action="store_true", dest="as_json")

    arm_live = operator_sub.add_parser("arm-live", help="Arm bounded live posture with explicit TTL")
    arm_live.add_argument("--deck", required=True)
    arm_live.add_argument("--ttl-seconds", required=True, type=int)
    arm_live.add_argument("--auth-profile", required=True)
    arm_live.add_argument("--session-id")
    arm_live.add_argument("--operator-id")
    arm_live.add_argument("--operator-note")
    arm_live.add_argument("--confirm-live", action="store_true")
    arm_live.add_argument("--state-file", default=".state/operator_posture.json")
    arm_live.add_argument("--receipt-dir", default=".state/operator_receipts")
    arm_live.add_argument("--json", action="store_true", dest="as_json")

    disarm_live = operator_sub.add_parser("disarm-live", help="Immediately disarm live posture")
    disarm_live.add_argument("--auth-profile")
    disarm_live.add_argument("--session-id")
    disarm_live.add_argument("--operator-id")
    disarm_live.add_argument("--operator-note")
    disarm_live.add_argument("--state-file", default=".state/operator_posture.json")
    disarm_live.add_argument("--receipt-dir", default=".state/operator_receipts")
    disarm_live.add_argument("--json", action="store_true", dest="as_json")

    flatten = operator_sub.add_parser("flatten", help="Issue bounded flatten action")
    flatten.add_argument(
        "--mode",
        required=True,
        choices=("emergency", "forced-exit", "final-auction"),
    )
    flatten.add_argument("--auth-profile")
    flatten.add_argument("--session-id")
    flatten.add_argument("--operator-id")
    flatten.add_argument("--operator-note")
    flatten.add_argument("--state-file", default=".state/operator_posture.json")
    flatten.add_argument("--receipt-dir", default=".state/operator_receipts")
    flatten.add_argument("--json", action="store_true", dest="as_json")

    submit_order_smoke = operator_sub.add_parser(
        "submit-order-smoke",
        help="Seed smoke command for order-gate refusal/acceptance receipts",
    )
    submit_order_smoke.add_argument("--symbol", required=True)
    submit_order_smoke.add_argument("--side", required=True, choices=("buy", "sell"))
    submit_order_smoke.add_argument("--quantity", required=True, type=int)
    submit_order_smoke.add_argument("--auth-profile")
    submit_order_smoke.add_argument("--session-id")
    submit_order_smoke.add_argument("--operator-id")
    submit_order_smoke.add_argument("--operator-note")
    submit_order_smoke.add_argument("--state-file", default=".state/operator_posture.json")
    submit_order_smoke.add_argument("--receipt-dir", default=".state/operator_receipts")
    submit_order_smoke.add_argument("--json", action="store_true", dest="as_json")

    live_smoke = operator_sub.add_parser(
        "live-smoke-readiness",
        help="Run the bounded live-capability smoke sequence and emit a pass/fail receipt bundle",
    )
    live_smoke.add_argument("--deck", required=True)
    live_smoke.add_argument("--auth-profile", required=True)
    live_smoke.add_argument("--ttl-seconds", type=int, default=300)
    live_smoke.add_argument("--symbol", default="2330")
    live_smoke.add_argument("--side", choices=("buy", "sell"), default="buy")
    live_smoke.add_argument("--quantity", type=int, default=1)
    live_smoke.add_argument(
        "--flatten-mode",
        choices=("emergency", "forced-exit", "final-auction"),
        default="forced-exit",
    )
    live_smoke.add_argument("--session-id")
    live_smoke.add_argument(
        "--trading-day-status",
        choices=("open", "closed", "unknown"),
        default="unknown",
    )
    live_smoke.add_argument(
        "--probe-json",
        help="Optional JSON health snapshot to gate live-smoke readiness using the canonical preflight contract",
    )
    live_smoke.add_argument(
        "--probe-source",
        choices=("seed", "steamer-cron-health"),
        help="Optional named probe source when no explicit --probe-json snapshot is supplied",
    )
    live_smoke.add_argument(
        "--probe-date",
        help="Optional Asia/Taipei probe date (YYYYMMDD) for named probe sources",
    )
    live_smoke.add_argument("--operator-id")
    live_smoke.add_argument("--operator-note")
    live_smoke.add_argument("--state-file", default=".state/operator_posture.json")
    live_smoke.add_argument("--receipt-dir", default=".state/operator_receipts")
    live_smoke.add_argument("--json", action="store_true", dest="as_json")

    preflight_smoke = operator_sub.add_parser(
        "preflight-smoke",
        help="Run the broker-preflight readiness gate and report whether the next live-preflight step is blocked or ready",
    )
    preflight_smoke.add_argument("--auth-profile", required=True)
    preflight_smoke.add_argument("--deck", required=True)
    preflight_smoke.add_argument(
        "--probe-json",
        help="Optional JSON health snapshot to replace seed not-connected session/probe fields",
    )
    preflight_smoke.add_argument(
        "--probe-source",
        choices=("seed", "steamer-cron-health"),
        help="Optional named probe source when no explicit --probe-json snapshot is supplied",
    )
    preflight_smoke.add_argument(
        "--probe-date",
        help="Optional Asia/Taipei probe date (YYYYMMDD) for named probe sources",
    )
    preflight_smoke.add_argument(
        "--trading-day-status",
        choices=("open", "closed", "unknown"),
        default="unknown",
    )
    preflight_smoke.add_argument("--session-id")
    preflight_smoke.add_argument("--state-file", default=".state/operator_posture.json")
    preflight_smoke.add_argument("--receipt-dir", default=".state/operator_receipts")
    preflight_smoke.add_argument("--json", action="store_true", dest="as_json")

    probe_session = operator_sub.add_parser(
        "probe-session",
        help="Emit a canonical session health snapshot for preflight/cron consumption",
    )
    probe_session.add_argument("--auth-profile", required=True)
    probe_session.add_argument(
        "--trading-day-status",
        choices=("open", "closed", "unknown"),
        default="unknown",
    )
    probe_session.add_argument("--session-id")
    probe_session.add_argument(
        "--probe-json",
        help="Optional external JSON snapshot to pass through the canonical probe-session surface",
    )
    probe_session.add_argument(
        "--probe-source",
        choices=("seed", "steamer-cron-health"),
        help="Optional named probe source when no explicit --probe-json snapshot is supplied",
    )
    probe_session.add_argument(
        "--probe-date",
        help="Optional Asia/Taipei probe date (YYYYMMDD) for named probe sources",
    )
    probe_session.add_argument(
        "--output",
        help="Optional path to write the emitted snapshot JSON for downstream cron/preflight use",
    )
    probe_session.add_argument("--json", action="store_true", dest="as_json")

    inspect = operator_sub.add_parser("inspect", help="Inspect a runtime target")
    inspect.add_argument("target", nargs="?", default="default")

    return parser


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _print_validation_success(manifest_type: str, path: str) -> None:
    print(f"OK: {manifest_type} manifest is valid -> {path}")


def _print_auth_summary(summary: dict) -> None:
    print("Auth Profile")
    print(f"  account: {summary['account']}")
    print(f"  mode: {summary['mode']} ({summary['auth_mode_label']})")
    print(
        "  capabilities: "
        f"marketdata={summary['marketdata_enabled']} "
        f"account_query={summary['account_query_enabled']} "
        f"trade={summary['trade_enabled']}"
    )
    print(f"  safety_boundary: {summary['safety_boundary']}")


def _seed_session_status(*, trading_day_status: str) -> dict:
    return {
        "session_state": "logical-profile-only",
        "renewal_state": "not-attached",
        "connected_surfaces": (),
        "degraded_surfaces": (),
        "connections": {
            "marketdata": {
                "state": "not-connected",
                "detail": "seed-runtime: marketdata transport not attached",
                "last_heartbeat_at": None,
                "last_error": None,
            },
            "broker": {
                "state": "not-connected",
                "detail": "seed-runtime: broker transport not attached",
                "last_heartbeat_at": None,
                "last_error": None,
            },
            "account": {
                "state": "not-connected",
                "detail": (
                    "seed-runtime: account-query surface not attached"
                    if trading_day_status != "unknown"
                    else "seed-runtime: account-query surface not attached; trading-day unresolved"
                ),
                "last_heartbeat_at": None,
                "last_error": None,
            },
        },
    }


def _tpe_probe_day() -> str:
    return datetime.now(TPE).strftime("%Y%m%d")


def _load_probe_snapshot(path: str | None) -> dict | None:
    if not path:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"probe snapshot must be a JSON object: {path}")
    observed_at = _probe_observed_at(payload)
    enriched = json.loads(json.dumps(payload))
    enriched["probe_source"] = str(payload.get("probe_source") or "external-json")
    enriched["probe_freshness"] = {
        "status": _probe_freshness_status(
            session_status=payload.get("session_status") if isinstance(payload.get("session_status"), dict) else {},
            receipt_kind="probe-json",
        ),
        "observed_at": observed_at,
        "detail": (
            f"probe-json supplied via {Path(path).resolve()}"
            if observed_at
            else f"probe-json supplied via {Path(path).resolve()} without an observation timestamp"
        ),
    }
    enriched["probe_receipt"] = {
        "kind": "probe-json",
        "path": str(Path(path).resolve()),
        "label": Path(path).name,
        "updated_at": observed_at,
    }
    return enriched


def _load_stage_state(path: Path) -> dict | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"stage state must be a JSON object: {path}")
    return payload


def _surface_state(
    state: str,
    detail: str,
    *,
    last_heartbeat_at: str | None = None,
    last_error: str | None = None,
) -> dict:
    return {
        "state": state,
        "detail": detail,
        "last_heartbeat_at": last_heartbeat_at,
        "last_error": last_error,
    }


def _probe_observed_at(snapshot: dict) -> str | None:
    captured_at = snapshot.get("captured_at")
    if isinstance(captured_at, str) and captured_at:
        return captured_at

    session_status = snapshot.get("session_status")
    if not isinstance(session_status, dict):
        return None

    latest_seen: datetime | None = None
    latest_value: str | None = None
    connections = session_status.get("connections")
    if not isinstance(connections, dict):
        return None

    for connection in connections.values():
        if not isinstance(connection, dict):
            continue
        raw = connection.get("last_heartbeat_at")
        if not isinstance(raw, str) or not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            continue
        if latest_seen is None or parsed > latest_seen:
            latest_seen = parsed
            latest_value = parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return latest_value


def _probe_freshness_status(*, session_status: dict, receipt_kind: str) -> str:
    if receipt_kind == "seed":
        return "seed-unverified"

    session_state = str(session_status.get("session_state") or "")
    renewal_state = str(session_status.get("renewal_state") or "")

    if session_state == "stale":
        return "stale"
    if session_state == "healthy" or renewal_state == "fresh":
        return "fresh"
    if session_state == "auth-required":
        return "blocked"
    if renewal_state in {"attention-needed", "blocked", "not-attached"}:
        return renewal_state
    if session_state == "logical-profile-only":
        return "not-attached"
    return session_state or renewal_state or "unknown"


def _build_probe_contract_snapshot(
    *,
    probe_source: str,
    session_status: dict,
    receipt_kind: str,
    receipt_path: Path | None,
    receipt_label: str,
    receipt_updated_at: str | None,
    freshness_detail: str,
) -> dict:
    observed_at = receipt_updated_at or _probe_observed_at({"session_status": session_status})
    return {
        "probe_source": probe_source,
        "session_status": session_status,
        "probe_freshness": {
            "status": _probe_freshness_status(session_status=session_status, receipt_kind=receipt_kind),
            "observed_at": observed_at,
            "detail": freshness_detail,
        },
        "probe_receipt": {
            "kind": receipt_kind,
            "path": str(receipt_path.resolve()) if receipt_path else None,
            "label": receipt_label,
            "updated_at": receipt_updated_at or observed_at,
        },
    }


def _seed_probe_freshness() -> dict:
    return {
        "status": "seed-unverified",
        "observed_at": None,
        "detail": "seed logical-session placeholders only; no source-backed receipt attached",
    }


def _seed_probe_receipt() -> dict:
    return {
        "kind": "seed",
        "path": None,
        "label": "seed-logical-session",
        "updated_at": None,
    }


def _critical_surface_session_state(marketdata_state: str, broker_state: str) -> tuple[str, str]:
    critical_states = (marketdata_state, broker_state)
    if any(state == "auth" for state in critical_states):
        return "auth-required", "blocked"
    if any(state == "stale" for state in critical_states):
        return "stale", "attention-needed"
    if any(state == "capability-mismatch" for state in critical_states):
        return "capability-mismatch", "not-attached"
    if all(state == "connected" for state in critical_states):
        return "healthy", "fresh"
    if any(state == "disconnected" for state in critical_states):
        return "disconnected", "attention-needed"
    if all(state == "not-connected" for state in critical_states):
        return "logical-profile-only", "not-attached"
    return "degraded", "attention-needed"


def _apply_connection_contract(summary: dict) -> dict:
    session_status = summary["session_status"]
    connections = session_status["connections"]
    capabilities = summary["capabilities"]

    if not capabilities.get("marketdata_enabled", False):
        connections["marketdata"] = _surface_state(
            "capability-mismatch",
            "auth profile disables marketdata surface",
        )
    if not capabilities.get("account_query_enabled", False):
        connections["account"] = _surface_state(
            "capability-mismatch",
            "auth profile disables account-query surface",
        )

    connected_surfaces: list[str] = []
    degraded_surfaces: list[str] = []
    for surface in (*CRITICAL_SURFACES, "account"):
        state = connections[surface].get("state", "not-connected")
        if state == "connected":
            connected_surfaces.append(surface)
        elif state in {"auth", "capability-mismatch", "disconnected", "stale"}:
            degraded_surfaces.append(surface)

    session_state, renewal_state = _critical_surface_session_state(
        connections["marketdata"].get("state", "not-connected"),
        connections["broker"].get("state", "not-connected"),
    )

    session_status["connected_surfaces"] = connected_surfaces
    session_status["degraded_surfaces"] = degraded_surfaces
    session_status["session_state"] = session_state
    session_status["renewal_state"] = renewal_state

    summary["health_status"]["session"] = session_state
    summary["health_status"]["marketdata_connection"] = connections["marketdata"].get("state", "not-connected")
    summary["health_status"]["broker_connection"] = connections["broker"].get("state", "not-connected")

    boundary = summary.setdefault("boundary", {})
    boundary["broker_connected"] = connections["broker"].get("state") == "connected"
    return summary


def _steamer_probe_snapshot_for_date(probe_date: str) -> dict:
    stage_dir = STEAMER_CRON_HEALTH_ROOT / probe_date / "stages"
    aws_auth_path = stage_dir / "aws_auth.json"
    ec2_power_on_path = stage_dir / "ec2_power_on.json"
    ec2_kickoff_path = stage_dir / "ec2_kickoff.json"
    ec2_verify_path = stage_dir / "ec2_verify.json"
    aws_auth = _load_stage_state(aws_auth_path)
    ec2_power_on = _load_stage_state(ec2_power_on_path)
    ec2_kickoff = _load_stage_state(ec2_kickoff_path)
    ec2_verify = _load_stage_state(ec2_verify_path)
    source = f"steamer-cron-health:{probe_date}"

    def stage_detail(stage: dict | None, fallback: str) -> str:
        if not stage:
            return fallback
        return str(stage.get("detail") or stage.get("reason") or fallback)

    def stage_updated(stage: dict | None) -> str | None:
        if not stage:
            return None
        raw = stage.get("updated_at")
        return str(raw) if raw else None

    def has_issue(stage: dict | None, token: str) -> bool:
        if not stage:
            return False
        blob = " ".join(
            str(stage.get(key) or "") for key in ("detail", "reason", "status")
        )
        return token in blob

    if not any((aws_auth, ec2_power_on, ec2_kickoff, ec2_verify)):
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": "logical-profile-only",
                "renewal_state": "not-attached",
                "connected_surfaces": [],
                "degraded_surfaces": [],
                "connections": {
                    "marketdata": _surface_state(
                        "not-connected",
                        f"upstream probe source missing under {stage_dir}",
                    ),
                    "broker": _surface_state(
                        "not-connected",
                        f"upstream probe source missing under {stage_dir}",
                    ),
                    "account": _surface_state(
                        "not-connected",
                        f"upstream probe source missing under {stage_dir}",
                    ),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=None,
            receipt_label=f"steamer-cron-health:{probe_date}:missing",
            receipt_updated_at=None,
            freshness_detail=f"no upstream steamer-cron-health receipt found under {stage_dir}",
        )

    if aws_auth and str(aws_auth.get("status")) != "success":
        detail = stage_detail(aws_auth, "aws_auth_not_ready")
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": "auth-required",
                "renewal_state": "blocked",
                "connected_surfaces": [],
                "degraded_surfaces": ["marketdata", "broker", "account"],
                "connections": {
                    "marketdata": _surface_state("auth", f"upstream aws auth blocked: {detail}", last_error=detail),
                    "broker": _surface_state("auth", f"upstream aws auth blocked: {detail}", last_error=detail),
                    "account": _surface_state("auth", f"upstream aws auth blocked: {detail}", last_error=detail),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=aws_auth_path,
            receipt_label=f"aws_auth:{probe_date}",
            receipt_updated_at=stage_updated(aws_auth),
            freshness_detail=f"steamer-cron-health blocked by aws_auth receipt: {detail}",
        )

    if ec2_verify and str(ec2_verify.get("status")) == "success":
        verify_at = stage_updated(ec2_verify)
        verify_detail = stage_detail(ec2_verify, "verify_green")
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": "healthy",
                "renewal_state": "fresh",
                "connected_surfaces": ["marketdata", "broker", "account"],
                "degraded_surfaces": [],
                "connections": {
                    "marketdata": _surface_state(
                        "connected",
                        f"upstream ec2_verify success: {verify_detail}",
                        last_heartbeat_at=verify_at,
                    ),
                    "broker": _surface_state(
                        "connected",
                        f"upstream live sim verified against broker-attached runtime: {verify_detail}",
                        last_heartbeat_at=verify_at,
                    ),
                    "account": _surface_state(
                        "not-connected",
                        "upstream source does not independently verify the account-query surface",
                        last_heartbeat_at=verify_at,
                    ),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=ec2_verify_path,
            receipt_label=f"ec2_verify:{probe_date}",
            receipt_updated_at=verify_at,
            freshness_detail=f"steamer-cron-health verified by ec2_verify receipt: {verify_detail}",
        )

    if ec2_verify:
        verify_detail = stage_detail(ec2_verify, "verify_not_ready")
        verify_at = stage_updated(ec2_verify)
        if has_issue(ec2_verify, "ticks_stale"):
            state = "stale"
            session_state = "stale"
            renewal_state = "attention-needed"
        elif has_issue(ec2_verify, "aws_auth"):
            state = "auth"
            session_state = "auth-required"
            renewal_state = "blocked"
        else:
            state = "disconnected"
            session_state = "disconnected"
            renewal_state = "attention-needed"
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": session_state,
                "renewal_state": renewal_state,
                "connected_surfaces": [],
                "degraded_surfaces": ["marketdata", "broker", "account"],
                "connections": {
                    "marketdata": _surface_state(state, f"upstream ec2_verify red: {verify_detail}", last_heartbeat_at=verify_at, last_error=verify_detail),
                    "broker": _surface_state(state, f"upstream ec2_verify red: {verify_detail}", last_heartbeat_at=verify_at, last_error=verify_detail),
                    "account": _surface_state(state, f"upstream ec2_verify red: {verify_detail}", last_heartbeat_at=verify_at, last_error=verify_detail),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=ec2_verify_path,
            receipt_label=f"ec2_verify:{probe_date}",
            receipt_updated_at=verify_at,
            freshness_detail=f"steamer-cron-health verify receipt is not green: {verify_detail}",
        )

    if ec2_kickoff and str(ec2_kickoff.get("status")) == "success":
        kickoff_at = stage_updated(ec2_kickoff)
        kickoff_detail = stage_detail(ec2_kickoff, "kickoff_started")
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": "degraded",
                "renewal_state": "attention-needed",
                "connected_surfaces": [],
                "degraded_surfaces": ["marketdata", "broker", "account"],
                "connections": {
                    "marketdata": _surface_state("disconnected", f"kickoff started but verify not yet green: {kickoff_detail}", last_heartbeat_at=kickoff_at),
                    "broker": _surface_state("disconnected", f"kickoff started but verify not yet green: {kickoff_detail}", last_heartbeat_at=kickoff_at),
                    "account": _surface_state("disconnected", f"kickoff started but verify not yet green: {kickoff_detail}", last_heartbeat_at=kickoff_at),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=ec2_kickoff_path,
            receipt_label=f"ec2_kickoff:{probe_date}",
            receipt_updated_at=kickoff_at,
            freshness_detail=f"steamer-cron-health kickoff receipt exists but verify is not yet green: {kickoff_detail}",
        )

    if ec2_power_on and str(ec2_power_on.get("status")) == "success":
        power_on_at = stage_updated(ec2_power_on)
        power_on_detail = stage_detail(ec2_power_on, "power_on_ready")
        return _build_probe_contract_snapshot(
            probe_source=source,
            session_status={
                "session_state": "degraded",
                "renewal_state": "attention-needed",
                "connected_surfaces": [],
                "degraded_surfaces": ["marketdata", "broker", "account"],
                "connections": {
                    "marketdata": _surface_state("disconnected", f"power-on ready but kickoff/verify not yet green: {power_on_detail}", last_heartbeat_at=power_on_at),
                    "broker": _surface_state("disconnected", f"power-on ready but kickoff/verify not yet green: {power_on_detail}", last_heartbeat_at=power_on_at),
                    "account": _surface_state("disconnected", f"power-on ready but kickoff/verify not yet green: {power_on_detail}", last_heartbeat_at=power_on_at),
                },
            },
            receipt_kind="steamer-cron-health-stage",
            receipt_path=ec2_power_on_path,
            receipt_label=f"ec2_power_on:{probe_date}",
            receipt_updated_at=power_on_at,
            freshness_detail=f"steamer-cron-health power-on receipt exists but kickoff/verify are not yet green: {power_on_detail}",
        )

    fallback_detail = stage_detail(aws_auth or ec2_power_on or ec2_kickoff or ec2_verify, "upstream stage unavailable")
    fallback_path = aws_auth_path if aws_auth else ec2_power_on_path if ec2_power_on else ec2_kickoff_path if ec2_kickoff else ec2_verify_path if ec2_verify else None
    fallback_updated_at = stage_updated(aws_auth or ec2_power_on or ec2_kickoff or ec2_verify)
    return _build_probe_contract_snapshot(
        probe_source=source,
        session_status={
            "session_state": "degraded",
            "renewal_state": "attention-needed",
            "connected_surfaces": [],
            "degraded_surfaces": ["marketdata", "broker", "account"],
            "connections": {
                "marketdata": _surface_state("disconnected", f"upstream stage not green: {fallback_detail}", last_error=fallback_detail),
                "broker": _surface_state("disconnected", f"upstream stage not green: {fallback_detail}", last_error=fallback_detail),
                "account": _surface_state("disconnected", f"upstream stage not green: {fallback_detail}", last_error=fallback_detail),
            },
        },
        receipt_kind="steamer-cron-health-stage",
        receipt_path=fallback_path,
        receipt_label=f"steamer-cron-health:{probe_date}:fallback",
        receipt_updated_at=fallback_updated_at,
        freshness_detail=f"steamer-cron-health fell back to a non-green stage receipt: {fallback_detail}",
    )


def _resolve_named_probe_source(*, probe_source: str | None, probe_date: str | None) -> dict | None:
    source = probe_source or os.environ.get("STEAMER_CARD_ENGINE_PROBE_SOURCE") or "seed"
    if source == "seed":
        return None
    if source == "steamer-cron-health":
        resolved_date = probe_date or os.environ.get("STEAMER_CARD_ENGINE_PROBE_DATE") or _tpe_probe_day()
        return _steamer_probe_snapshot_for_date(resolved_date)
    raise ValueError(f"unsupported probe source: {source}")


def _resolve_probe_snapshot(
    *,
    probe_json_path: str | None,
    probe_source: str | None,
    probe_date: str | None,
) -> dict | None:
    if probe_json_path:
        return _load_probe_snapshot(probe_json_path)
    return _resolve_named_probe_source(probe_source=probe_source, probe_date=probe_date)


def _merge_probe_snapshot(*, summary: dict, probe_snapshot: dict | None) -> dict:
    if not probe_snapshot:
        return _apply_connection_contract(summary)

    merged = json.loads(json.dumps(summary))
    session_status = probe_snapshot.get("session_status")
    if isinstance(session_status, dict):
        merged["session_status"] = session_status
        connections = session_status.get("connections") if isinstance(session_status.get("connections"), dict) else {}
        merged["health_status"]["session"] = session_status.get("session_state", merged["health_status"]["session"])
        if isinstance(connections.get("marketdata"), dict):
            merged["health_status"]["marketdata_connection"] = connections["marketdata"].get(
                "state", merged["health_status"]["marketdata_connection"]
            )
        if isinstance(connections.get("broker"), dict):
            merged["health_status"]["broker_connection"] = connections["broker"].get(
                "state", merged["health_status"]["broker_connection"]
            )

    capabilities = probe_snapshot.get("capabilities")
    if isinstance(capabilities, dict):
        merged["capabilities"].update(capabilities)

    boundary = merged.setdefault("boundary", {})
    boundary["probe_source"] = probe_snapshot.get("probe_source", "external-json")
    boundary["probe_freshness"] = probe_snapshot.get("probe_freshness", _seed_probe_freshness())
    boundary["probe_receipt"] = probe_snapshot.get("probe_receipt", _seed_probe_receipt())
    return _apply_connection_contract(merged)


def _inspect_logical_session(
    *,
    auth_profile_path: str,
    session_id: str | None,
    trading_day_status: str,
    probe_json_path: str | None = None,
    probe_source: str | None = None,
    probe_date: str | None = None,
) -> dict:
    profile = load_auth_profile(auth_profile_path)
    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    live_allowed = trading_day_status == "open"
    session_status = _seed_session_status(trading_day_status=trading_day_status)
    summary = {
        "session_id": session_id or "seed-logical-session",
        "account_no": profile.account,
        "auth_mode": profile.mode,
        "auth_profile": auth_profile_path,
        "session_started_at": now,
        "expires_at": None,
        "renewal_hint": "seed-runtime: real broker/session renewal not attached",
        "session_status": session_status,
        "capabilities": {
            "marketdata_enabled": profile.marketdata_enabled,
            "account_query_enabled": profile.account_query_enabled,
            "trade_enabled": profile.trade_enabled,
        },
        "health_status": {
            "runtime": "seed-ok",
            "session": session_status["session_state"],
            "marketdata_connection": session_status["connections"]["marketdata"]["state"],
            "broker_connection": session_status["connections"]["broker"]["state"],
        },
        "trading_day_gate": {
            "status": trading_day_status,
            "live_allowed": live_allowed,
            "reason": (
                "trading-day-open"
                if trading_day_status == "open"
                else "trading-day-closed"
                if trading_day_status == "closed"
                else "trading-day-unknown"
            ),
            "source": "seed-operator-input",
        },
        "boundary": {
            "activation": "prepared-only",
            "broker_connected": False,
            "probe_freshness": _seed_probe_freshness(),
            "probe_receipt": _seed_probe_receipt(),
            "notes": "logical session inspection only; does not establish a live broker/runtime session",
        },
    }
    probe_snapshot = _resolve_probe_snapshot(
        probe_json_path=probe_json_path,
        probe_source=probe_source,
        probe_date=probe_date,
    )
    return _merge_probe_snapshot(summary=summary, probe_snapshot=probe_snapshot)


def _print_auth_session_summary(summary: dict) -> None:
    capabilities = summary["capabilities"]
    gate = summary["trading_day_gate"]
    health = summary["health_status"]
    session_status = summary["session_status"]
    print("Logical Session")
    print(
        "  session: "
        f"id={summary['session_id']} account={summary['account_no']} auth_mode={summary['auth_mode']}"
    )
    print(
        "  capabilities: "
        f"marketdata={capabilities['marketdata_enabled']} "
        f"account_query={capabilities['account_query_enabled']} trade={capabilities['trade_enabled']}"
    )
    print(
        "  health: "
        f"runtime={health['runtime']} session={health['session']} "
        f"marketdata={health['marketdata_connection']} broker={health['broker_connection']}"
    )
    print(
        "  session_status: "
        f"state={session_status['session_state']} renewal={session_status['renewal_state']}"
    )
    print(
        "  trading_day_gate: "
        f"status={gate['status']} live_allowed={gate['live_allowed']} reason={gate['reason']}"
    )
    print(f"  activation: {summary['boundary']['activation']}")


def _probe_session_snapshot(*, logical_session: dict) -> dict:
    boundary = logical_session.get("boundary", {})
    return {
        "probe_source": boundary.get("probe_source", "operator-probe-session:seed"),
        "captured_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "auth_profile": logical_session["auth_profile"],
        "session_id": logical_session["session_id"],
        "account_no": logical_session["account_no"],
        "auth_mode": logical_session["auth_mode"],
        "capabilities": logical_session["capabilities"],
        "health_status": logical_session["health_status"],
        "session_status": logical_session["session_status"],
        "trading_day_gate": logical_session["trading_day_gate"],
        "probe_freshness": boundary.get("probe_freshness", _seed_probe_freshness()),
        "probe_receipt": boundary.get("probe_receipt", _seed_probe_receipt()),
        "boundary": {
            "activation": boundary.get("activation", "prepared-only"),
            "broker_connected": boundary.get("broker_connected", False),
            "notes": "canonical probe snapshot for operator preflight consumers",
        },
    }


def _write_probe_snapshot(path: str | None, snapshot: dict) -> str | None:
    if not path:
        return None
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return str(output_path)


def _print_probe_session_summary(snapshot: dict, output_path: str | None) -> None:
    session_status = snapshot["session_status"]
    connections = session_status["connections"]
    gate = snapshot["trading_day_gate"]
    print("Operator Probe Session")
    print(
        "  session: "
        f"id={snapshot['session_id']} account={snapshot['account_no']} auth_mode={snapshot['auth_mode']}"
    )
    print(f"  probe_source: {snapshot['probe_source']}")
    print(
        "  probe_freshness: "
        f"status={snapshot['probe_freshness']['status']} observed_at={snapshot['probe_freshness']['observed_at']}"
    )
    print(
        "  probe_receipt: "
        f"label={snapshot['probe_receipt']['label']} path={snapshot['probe_receipt']['path']}"
    )
    print(
        "  connections: "
        f"marketdata={connections['marketdata']['state']} "
        f"broker={connections['broker']['state']} account={connections['account']['state']}"
    )
    print(
        "  trading_day_gate: "
        f"status={gate['status']} live_allowed={gate['live_allowed']}"
    )
    if output_path:
        print(f"  output: {output_path}")


def _print_card_summary(summary: dict) -> None:
    print("Card Manifest")
    print(f"  id: {summary['card_id']}  version: {summary['version']}  status: {summary['status']}")
    print(f"  name: {summary['name']}  family: {summary['strategy_family']}")
    print(f"  symbols ({len(summary['symbol_pool'])}): {', '.join(summary['symbol_pool'])}")
    print(
        "  features "
        f"({len(summary['feature_requirements'])}): {', '.join(summary['feature_requirements'])}"
    )
    print(f"  parameter_keys: {', '.join(summary['parameter_keys']) or '(none)'}")


def _print_deck_summary(summary: dict) -> None:
    print("Deck Manifest")
    print(f"  id: {summary['deck_id']}  market: {summary['market']}  session: {summary['session']}")
    print(f"  auth_profile: {summary['auth_profile']}")
    print(f"  enabled_cards ({summary['cards_total']}): {', '.join(summary['enabled_cards'])}")
    if summary["missing_cards"]:
        print(f"  missing_cards: {', '.join(summary['missing_cards'])}")
    print(f"  symbol_scope ({len(summary['symbol_scope'])}): {', '.join(summary['symbol_scope'])}")
    print(
        "  merged_symbol_scope "
        f"({len(summary['merged_symbol_scope'])}): {', '.join(summary['merged_symbol_scope'])}"
    )
    if summary["merged_feature_requirements"]:
        print(
            "  merged_feature_requirements: "
            f"{', '.join(summary['merged_feature_requirements'])}"
        )


def _print_global_summary(summary: dict) -> None:
    print("Global Config")
    print(f"  market/session: {summary['market']} / {summary['session']}")
    print(f"  live_enabled={summary['live_enabled']} dry_run={summary['dry_run']}")
    print(
        "  adapters: "
        f"market_data={summary['market_data_adapter']} broker={summary['broker_adapter']}"
    )
    print(f"  active_account: {summary['active_account']}  auth_profile: {summary['auth_profile']}")

    final_auction = summary["flatten_policy"]["final_auction"]
    if final_auction:
        print(
            "  final_auction: "
            f"enabled={final_auction['enabled']} window={final_auction['window']} "
            f"order_style={final_auction['order_style']}"
        )

    emergency_stop = summary["risk"]["emergency_stop"]
    if emergency_stop:
        print(
            "  emergency_stop: "
            f"mode={emergency_stop['mode']} value={emergency_stop['value']}"
        )


def _print_catalog_summary(summary: dict) -> None:
    print("Strategy Catalog Metadata")
    print(f"  schema_version: {summary['schema_version']}")
    if summary.get("catalog_id"):
        print(f"  catalog_id: {summary['catalog_id']}")
    if summary.get("updated_at"):
        print(f"  updated_at: {summary['updated_at']}")
    print(f"  strategies_total: {summary['strategies_total']}")
    regimes = summary.get("market_regimes") or []
    if regimes:
        print(f"  market_regimes ({len(regimes)}): {', '.join(regimes)}")


def _print_operator_status_summary(payload: dict) -> None:
    print("Operator Status")
    session = payload["session"]
    capabilities = payload["capabilities"]
    gate = payload["order_submission_gate"]

    print(f"  mode: {payload['mode']}")
    print(
        "  session: "
        f"id={session['session_id']} account={session['account_no']} auth_mode={session['auth_mode']}"
    )
    print(
        "  capabilities: "
        f"marketdata={capabilities['marketdata_enabled']} "
        f"account_query={capabilities['account_query_enabled']} trade={capabilities['trade_enabled']}"
    )
    print(f"  armed_live: {payload['armed_live']}")
    if payload.get("armed_scope"):
        scope = payload["armed_scope"]
        print(
            "  armed_scope: "
            f"deck_id={scope['deck_id']} expires_at={scope['expires_at']} ttl={scope['ttl_seconds']}"
        )
    else:
        print("  armed_scope: (none)")
    print(f"  order_submission_gate: allowed={gate['allowed']} reason={gate['reason']}")


def _print_operator_action_summary(payload: dict) -> None:
    if payload.get("ok"):
        print("OK")
    else:
        print("REFUSED")

    for key in (
        "error",
        "armed_live",
        "was_armed",
        "flatten_mode",
        "implicit_disarm",
        "dispatch",
        "receipt_path",
    ):
        if key in payload:
            print(f"  {key}: {payload[key]}")


def _surface_blocker_code(surface: str, state: str) -> str:
    if state == "auth":
        return f"{surface}-auth"
    if state == "stale":
        return f"{surface}-stale"
    if state == "capability-mismatch":
        return f"{surface}-capability-mismatch"
    if state == "disconnected":
        return f"{surface}-disconnected"
    return f"{surface}-not-connected"


def _operator_preflight_smoke(
    *,
    auth_profile_path: str,
    deck_ref: str,
    trading_day_status: str,
    state_file: Path,
    receipt_dir: Path,
    session_id: str | None,
    probe_json_path: str | None,
    probe_source: str | None,
    probe_date: str | None,
) -> tuple[dict, int]:
    logical_session = _inspect_logical_session(
        auth_profile_path=auth_profile_path,
        session_id=session_id,
        trading_day_status=trading_day_status,
        probe_json_path=probe_json_path,
        probe_source=probe_source,
        probe_date=probe_date,
    )
    operator_result = operator_status(
        state_file=state_file,
        receipt_dir=receipt_dir,
        auth_profile_path=auth_profile_path,
        session_id=session_id,
    )

    blockers: list[dict[str, str]] = []
    capabilities = logical_session["capabilities"]
    session_status = logical_session["session_status"]
    gate = logical_session["trading_day_gate"]
    operator_payload = operator_result.payload

    if not gate["live_allowed"]:
        blockers.append({"code": "trading-day-gate", "detail": gate["reason"]})
    if not capabilities["marketdata_enabled"]:
        blockers.append({"code": "capability-marketdata-disabled", "detail": "marketdata_enabled=false"})
    if not capabilities["trade_enabled"]:
        blockers.append({"code": "capability-trade-disabled", "detail": "trade_enabled=false"})
    marketdata_state = session_status["connections"]["marketdata"]["state"]
    broker_state = session_status["connections"]["broker"]["state"]
    if marketdata_state != "connected":
        blockers.append({"code": _surface_blocker_code("marketdata", marketdata_state), "detail": marketdata_state})
    if broker_state != "connected":
        blockers.append({"code": _surface_blocker_code("broker", broker_state), "detail": broker_state})
    if operator_payload["armed_live"]:
        blockers.append({"code": "operator-posture-armed", "detail": "preflight requires disarmed baseline"})
    if operator_payload["order_submission_gate"]["reason"] != "disarmed-posture":
        blockers.append({
            "code": "unexpected-order-gate",
            "detail": operator_payload["order_submission_gate"]["reason"],
        })

    ready = not blockers
    payload = {
        "ok": ready,
        "preflight_status": "ready" if ready else "blocked",
        "activation": "prepared-only",
        "deck": deck_ref,
        "auth_profile": auth_profile_path,
        "logical_session": logical_session,
        "probe_freshness": logical_session["boundary"].get("probe_freshness", _seed_probe_freshness()),
        "probe_receipt": logical_session["boundary"].get("probe_receipt", _seed_probe_receipt()),
        "operator_status": operator_payload,
        "blockers": blockers,
        "next_command_map": {
            "probe_session": (
                f"steamer-card-engine operator probe-session --auth-profile {auth_profile_path} "
                f"--trading-day-status {trading_day_status} --json"
            ),
            "inspect_session": (
                f"steamer-card-engine auth inspect-session --auth-profile {auth_profile_path} "
                f"--trading-day-status {trading_day_status} --json"
            ),
            "operator_status": (
                f"steamer-card-engine operator status --auth-profile {auth_profile_path} --json"
            ),
            "bounded_live_smoke": (
                f"steamer-card-engine operator live-smoke-readiness --deck {deck_ref} "
                f"--auth-profile {auth_profile_path} --json"
            ),
        },
        "replacement_contract": {
            "expected_connected_surfaces": ["marketdata", "broker"],
            "session_status_source": "replace seed placeholders with adapter/session-manager health snapshots",
        },
        "boundary": "seed preflight gate only; no broker/session attach is performed here",
    }
    return payload, 0 if ready else 4


def _live_smoke_preflight_step(*, payload: dict, exit_code: int) -> dict:
    return {
        "step": "preflight-smoke-gate",
        "ok": exit_code == 0 and bool(payload.get("ok")),
        "exit_code": exit_code,
        "expected_exit_code": 0,
        "payload": payload,
    }


def _blocked_live_smoke_payload(*, preflight_payload: dict, preflight_exit_code: int) -> dict:
    preflight_step = _live_smoke_preflight_step(payload=preflight_payload, exit_code=preflight_exit_code)
    return {
        "ok": False,
        "smoke_status": "blocked",
        "activation": "prepared-only",
        "probe_freshness": preflight_payload.get("probe_freshness", _seed_probe_freshness()),
        "probe_receipt": preflight_payload.get("probe_receipt", _seed_probe_receipt()),
        "error": "live smoke readiness blocked by preflight gate",
        "failed_step": preflight_step,
        "steps": [preflight_step],
        "preflight": preflight_payload,
        "boundary": (
            "prepared-only smoke sequence; broker-preflight gate must be ready before "
            "bounded arm/submit/flatten checks"
        ),
    }


def _handle_catalog_error(error: StrategyCatalogValidationError) -> int:
    print(f"Validation failed for strategy catalog metadata: {error.path}", flush=True)
    for issue in error.errors:
        print(f"- {issue}", flush=True)
    return 2


def _handle_manifest_error(error: ManifestValidationError) -> int:
    print(
        f"Validation failed for {error.manifest_type} manifest: {error.path}",
        flush=True,
    )
    for issue in error.errors:
        print(f"- {issue}", flush=True)
    return 2


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered)
    return slug.strip("-")


def _default_scenario_id(session_date: str) -> str:
    return f"tw-paper-sim.twse.{session_date}.full-session"


def _default_live_scenario_id(session_date: str) -> str:
    return f"tw-live-sim.twse.{session_date}.full-session"


def _run_timestamp_utc() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _emit_replay_candidate_bundle(args: argparse.Namespace) -> dict:
    load_deck_manifest(args.deck)

    session_date = args.date
    scenario_id = args.scenario_id or _default_scenario_id(session_date)
    scenario_slug = _slugify(scenario_id)
    run_id = args.run_id or f"replay-sim_{scenario_slug}_candidate_{_run_timestamp_utc()}"

    baseline_dir = Path(args.baseline_dir)
    if not baseline_dir.exists():
        raise SimCompareError(
            "candidate replay baseline source not found: "
            f"{baseline_dir} (override with --baseline-dir)"
        )

    output_root = Path(args.output_root)
    output_dir = output_root / "steamer-card-engine" / session_date / run_id

    if args.dry_run:
        return {
            "mode": "dry-run",
            "deck": args.deck,
            "session_date": session_date,
            "scenario_id": scenario_id,
            "baseline_dir": str(baseline_dir.resolve()),
            "output_dir": str(output_dir.resolve()),
            "run_id": run_id,
        }

    summary = normalize_baseline_bundle(
        baseline_dir=baseline_dir,
        output_dir=output_dir,
        session_date=session_date,
        scenario_id=scenario_id,
        run_id=run_id,
        lane="steamer-card-engine",
        scenario_spec_path=Path(args.scenario_spec) if args.scenario_spec else None,
        max_events=args.max_events,
        max_decisions=args.max_decisions,
        fill_model=args.fill_model,
        engine_name="steamer-card-engine-replay-runner",
        emitter_name="steamer-card-engine replay run",
        emitter_version="m1-replay-runner/v0",
        determinism_note="derived by baseline normalizer from legacy artifacts",
        config_snapshot_actor_key="emitter",
    )
    summary["mode"] = "replay"
    summary["baseline_dir"] = str(baseline_dir.resolve())
    return summary


def _emit_live_sim_bundle(args: argparse.Namespace) -> dict:
    load_deck_manifest(args.deck)

    session_date = args.session_date
    scenario_id = args.scenario_id or _default_live_scenario_id(session_date)
    scenario_slug = _slugify(scenario_id)
    run_id = args.run_id or f"live-sim_{scenario_slug}_candidate_{_run_timestamp_utc()}"

    baseline_dir = Path(args.baseline_dir)
    if not baseline_dir.exists():
        raise SimCompareError(
            "live-sim baseline capture not found: "
            f"{baseline_dir} (override with --baseline-dir)"
        )

    output_root = Path(args.output_root)
    output_dir = output_root / "steamer-card-engine" / session_date / run_id

    if args.dry_run:
        return {
            "mode": "dry-run",
            "run_type": "live-sim",
            "deck": args.deck,
            "session_date": session_date,
            "scenario_id": scenario_id,
            "baseline_dir": str(baseline_dir.resolve()),
            "output_dir": str(output_dir.resolve()),
            "run_id": run_id,
            "capability_posture": {"trade_enabled": False},
        }

    market_source_id = f"live-sim-capture:{baseline_dir.resolve()}"
    deck_manifest = load_deck_manifest(args.deck)
    deck_cards = [{"card_id": card_id, "card_version": "manifest/v0"} for card_id in deck_manifest.cards]

    summary = normalize_baseline_bundle(
        baseline_dir=baseline_dir,
        output_dir=output_dir,
        session_date=session_date,
        scenario_id=scenario_id,
        run_type="live-sim",
        market_event_source_id=market_source_id,
        market_event_source_kind="recorded-stream",
        market_event_source_ref=str(baseline_dir.resolve()),
        run_id=run_id,
        lane="steamer-card-engine",
        scenario_spec_path=Path(args.scenario_spec) if args.scenario_spec else None,
        max_events=args.max_events,
        max_decisions=args.max_decisions,
        fill_model=args.fill_model,
        engine_name="steamer-card-engine-live-sim-runner",
        emitter_name="steamer-card-engine sim run-live",
        emitter_version="m1-live-sim-runner/v0",
        determinism_note=(
            "derived from a captured market-event stream; M1 bridge uses offline consumption "
            "(no broker submission semantics)"
        ),
        config_snapshot_actor_key="emitter",
        deck_id=deck_manifest.deck_id,
        deck_version="manifest/v0",
        cards=deck_cards,
        global_config_version="manifest/v0",
    )
    summary["mode"] = "live-sim"
    summary["baseline_dir"] = str(baseline_dir.resolve())
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "auth" and args.auth_command == "validate-profile":
            load_auth_profile(args.path)
            _print_validation_success("auth profile", args.path)
            return 0

        if args.command == "auth" and args.auth_command == "inspect-profile":
            profile = load_auth_profile(args.path)
            summary = summarize_auth_profile(profile)
            if args.as_json:
                _print_json(summary)
            else:
                _print_auth_summary(summary)
            return 0

        if args.command == "auth" and args.auth_command == "inspect-session":
            summary = _inspect_logical_session(
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                trading_day_status=args.trading_day_status,
                probe_json_path=args.probe_json,
                probe_source=args.probe_source,
                probe_date=args.probe_date,
            )
            if args.as_json:
                _print_json(summary)
            else:
                _print_auth_session_summary(summary)
            return 0

        if args.command == "author" and args.author_command == "init-card":
            print(f"Scaffold placeholder for card: {args.name}")
            return 0

        if args.command == "author" and args.author_command == "validate-card":
            load_card_manifest(args.path)
            _print_validation_success("card", args.path)
            return 0

        if args.command == "author" and args.author_command == "inspect-card":
            card = load_card_manifest(args.path)
            summary = summarize_card_manifest(card)
            if args.as_json:
                _print_json(summary)
            else:
                _print_card_summary(summary)
            return 0

        if args.command == "author" and args.author_command == "validate-deck":
            load_deck_manifest(args.path)
            _print_validation_success("deck", args.path)
            return 0

        if args.command == "author" and args.author_command == "inspect-deck":
            deck = load_deck_manifest(args.path)
            cards = load_cards_from_dir(args.cards_dir)
            summary = summarize_deck_manifest(deck, cards_by_id=cards)
            if args.as_json:
                _print_json(summary)
            else:
                _print_deck_summary(summary)
            return 0

        if args.command == "author" and args.author_command == "validate-global":
            load_global_config(args.path)
            _print_validation_success("global", args.path)
            return 0

        if args.command == "author" and args.author_command == "inspect-global":
            config = load_global_config(args.path)
            summary = summarize_global_config(config)
            if args.as_json:
                _print_json(summary)
            else:
                _print_global_summary(summary)
            return 0

        if args.command == "catalog" and args.catalog_command == "validate":
            load_strategy_catalog(args.path)
            _print_validation_success("strategy catalog metadata", args.path)
            return 0

        if args.command == "catalog" and args.catalog_command == "inspect":
            catalog = load_strategy_catalog(args.path)
            summary = summarize_strategy_catalog(catalog)
            if args.as_json:
                _print_json(summary)
            else:
                _print_catalog_summary(summary)
            return 0

        if args.command == "catalog" and args.catalog_command == "query":
            catalog = load_strategy_catalog(args.path)
            matches = query_strategies_by_regime(catalog, args.regimes)
            if args.limit is not None:
                matches = matches[: max(0, args.limit)]

            if args.as_json:
                payload = {
                    "regimes": args.regimes,
                    "matches_total": len(matches),
                    "matches": [
                        {
                            "card_id": entry.card_id,
                            "display_name": entry.display_name,
                            "default_priority": entry.default_priority,
                            "market_regimes": entry.market_regimes,
                        }
                        for entry in matches
                    ],
                }
                _print_json(payload)
            else:
                for entry in matches:
                    label = entry.display_name or ""
                    if label:
                        print(f"{entry.card_id}\t{label}")
                    else:
                        print(entry.card_id)
            return 0

        if args.command == "replay" and args.replay_command == "run":
            summary = _emit_replay_candidate_bundle(args)
            if args.as_json:
                _print_json(summary)
            else:
                if summary.get("mode") == "dry-run":
                    print(
                        "Replay dry-run "
                        f"run_id={summary['run_id']} baseline={summary['baseline_dir']} "
                        f"output={summary['output_dir']}"
                    )
                else:
                    print(
                        "Replay bundle emitted "
                        f"run_id={summary['run_id']} output={summary['bundle_dir']} "
                        f"anomalies={summary['counts']['anomalies']}"
                    )
            return 0

        if args.command == "sim" and args.sim_command == "run-live":
            summary = _emit_live_sim_bundle(args)
            if args.as_json:
                _print_json(summary)
            else:
                if summary.get("mode") == "dry-run":
                    print(
                        "Live-sim dry-run "
                        f"run_id={summary['run_id']} capture={summary['baseline_dir']} "
                        f"output={summary['output_dir']}"
                    )
                else:
                    print(
                        "Live-sim bundle emitted "
                        f"run_id={summary['run_id']} output={summary['bundle_dir']} "
                        f"anomalies={summary['counts']['anomalies']}"
                    )
            return 0

        if args.command == "sim" and args.sim_command == "normalize-baseline":
            summary = normalize_baseline_bundle(
                baseline_dir=Path(args.baseline_dir),
                output_dir=Path(args.output_dir),
                session_date=args.session_date,
                scenario_id=args.scenario_id,
                run_id=args.run_id,
                lane=args.lane,
                scenario_spec_path=Path(args.scenario_spec) if args.scenario_spec else None,
                max_events=args.max_events,
                max_decisions=args.max_decisions,
                fill_model=args.fill_model,
            )
            if args.as_json:
                _print_json(summary)
            else:
                print(
                    "Normalized baseline bundle "
                    f"run_id={summary['run_id']} output={summary['bundle_dir']} "
                    f"anomalies={summary['counts']['anomalies']}"
                )
            return 0

        if args.command == "sim" and args.sim_command == "compare":
            summary = compare_bundles(
                baseline=Path(args.baseline),
                candidate=Path(args.candidate),
                output_dir=Path(args.output_dir),
                require_scenario_fingerprint=not args.allow_missing_fingerprint,
            )
            if args.as_json:
                _print_json(summary)
            else:
                print(
                    "Comparator "
                    f"status={summary['status']} output={summary['output_dir']} "
                    f"hard_fails={len(summary['hard_fail_reasons'])}"
                )
            return 0 if summary["status"] == "pass" else 3

        if args.command == "operator" and args.operator_command == "status":
            result = operator_status(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
            )
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_status_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "arm-live":
            result = operator_arm_live(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                deck_ref=args.deck,
                ttl_seconds=args.ttl_seconds,
                operator_id=args.operator_id,
                operator_note=args.operator_note,
                confirm_live=args.confirm_live,
            )
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_action_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "disarm-live":
            result = operator_disarm_live(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                operator_id=args.operator_id,
                operator_note=args.operator_note,
            )
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_action_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "flatten":
            result = operator_flatten(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                mode=args.mode,
                operator_id=args.operator_id,
                operator_note=args.operator_note,
            )
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_action_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "submit-order-smoke":
            result = operator_submit_order_smoke(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                operator_id=args.operator_id,
                operator_note=args.operator_note,
            )
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_action_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "live-smoke-readiness":
            preflight_payload, preflight_exit = _operator_preflight_smoke(
                auth_profile_path=args.auth_profile,
                deck_ref=args.deck,
                trading_day_status=args.trading_day_status,
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                session_id=args.session_id,
                probe_json_path=args.probe_json,
                probe_source=args.probe_source,
                probe_date=args.probe_date,
            )
            if preflight_exit != 0:
                payload = _blocked_live_smoke_payload(
                    preflight_payload=preflight_payload,
                    preflight_exit_code=preflight_exit,
                )
                if args.as_json:
                    _print_json(payload)
                else:
                    _print_operator_action_summary(payload)
                return preflight_exit

            result = operator_live_smoke_readiness(
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                deck_ref=args.deck,
                ttl_seconds=args.ttl_seconds,
                symbol=args.symbol,
                side=args.side,
                quantity=args.quantity,
                flatten_mode=args.flatten_mode,
                operator_id=args.operator_id,
                operator_note=args.operator_note,
            )
            preflight_step = _live_smoke_preflight_step(payload=preflight_payload, exit_code=preflight_exit)
            existing_steps = result.payload.get("steps")
            if isinstance(existing_steps, list):
                result.payload["steps"] = [preflight_step, *existing_steps]
            else:
                result.payload["steps"] = [preflight_step]
            result.payload["preflight"] = preflight_payload
            result.payload["probe_freshness"] = preflight_payload.get("probe_freshness", _seed_probe_freshness())
            result.payload["probe_receipt"] = preflight_payload.get("probe_receipt", _seed_probe_receipt())
            if args.as_json:
                _print_json(result.payload)
            else:
                _print_operator_action_summary(result.payload)
            return result.exit_code

        if args.command == "operator" and args.operator_command == "preflight-smoke":
            payload, exit_code = _operator_preflight_smoke(
                auth_profile_path=args.auth_profile,
                deck_ref=args.deck,
                trading_day_status=args.trading_day_status,
                state_file=Path(args.state_file),
                receipt_dir=Path(args.receipt_dir),
                session_id=args.session_id,
                probe_json_path=args.probe_json,
                probe_source=args.probe_source,
                probe_date=args.probe_date,
            )
            if args.as_json:
                _print_json(payload)
            else:
                _print_operator_action_summary(payload)
            return exit_code

        if args.command == "operator" and args.operator_command == "probe-session":
            logical_session = _inspect_logical_session(
                auth_profile_path=args.auth_profile,
                session_id=args.session_id,
                trading_day_status=args.trading_day_status,
                probe_json_path=args.probe_json,
                probe_source=args.probe_source,
                probe_date=args.probe_date,
            )
            snapshot = _probe_session_snapshot(logical_session=logical_session)
            output_path = _write_probe_snapshot(args.output, snapshot)
            if args.as_json:
                payload = dict(snapshot)
                if output_path:
                    payload["output_path"] = output_path
                _print_json(payload)
            else:
                _print_probe_session_summary(snapshot, output_path)
            return 0

    except StrategyCatalogValidationError as error:
        return _handle_catalog_error(error)
    except ManifestValidationError as error:
        return _handle_manifest_error(error)
    except SimCompareError as error:
        print(f"SIM comparability command failed: {error}", flush=True)
        return 2

    if args.command == "operator" and args.operator_command == "inspect":
        print(f"Inspect placeholder for target={args.target}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
