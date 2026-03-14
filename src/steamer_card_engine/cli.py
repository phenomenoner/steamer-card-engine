from __future__ import annotations

import argparse
import json
from pathlib import Path

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
from steamer_card_engine.sim_compare import (
    SimCompareError,
    compare_bundles,
    normalize_baseline_bundle,
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

    replay = subparsers.add_parser("replay", help="Replay and analysis commands")
    replay_sub = replay.add_subparsers(dest="replay_command", required=True)
    replay_run = replay_sub.add_parser("run", help="Run a replay job")
    replay_run.add_argument("--deck", required=True)
    replay_run.add_argument("--date", required=True)
    replay_run.add_argument("--dry-run", action="store_true")

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
    operator_sub.add_parser("status", help="Inspect runtime posture")
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


def _handle_manifest_error(error: ManifestValidationError) -> int:
    print(
        f"Validation failed for {error.manifest_type} manifest: {error.path}",
        flush=True,
    )
    for issue in error.errors:
        print(f"- {issue}", flush=True)
    return 2


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

    except ManifestValidationError as error:
        return _handle_manifest_error(error)
    except SimCompareError as error:
        print(f"SIM comparability command failed: {error}", flush=True)
        return 2

    if args.command == "replay" and args.replay_command == "run":
        mode = "dry-run" if args.dry_run else "replay"
        print(f"Placeholder {mode} job for deck={args.deck} date={args.date}")
        return 0

    if args.command == "operator" and args.operator_command == "status":
        print("Status placeholder: no runtime attached yet; seed repo is docs/scaffold first.")
        return 0

    if args.command == "operator" and args.operator_command == "inspect":
        print(f"Inspect placeholder for target={args.target}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
