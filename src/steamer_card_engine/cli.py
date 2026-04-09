from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re

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
