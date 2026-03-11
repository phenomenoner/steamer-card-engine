from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steamer-card-engine",
        description="Card-oriented runtime seed for Taiwan cash intraday strategy operations.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    author = subparsers.add_parser("author", help="Authoring and validation commands")
    author_sub = author.add_subparsers(dest="author_command", required=True)
    init_card = author_sub.add_parser("init-card", help="Scaffold a new card definition")
    init_card.add_argument("name")
    validate_card = author_sub.add_parser("validate-card", help="Validate a card manifest path")
    validate_card.add_argument("path")

    replay = subparsers.add_parser("replay", help="Replay and analysis commands")
    replay_sub = replay.add_subparsers(dest="replay_command", required=True)
    replay_run = replay_sub.add_parser("run", help="Run a replay job")
    replay_run.add_argument("--deck", required=True)
    replay_run.add_argument("--date", required=True)
    replay_run.add_argument("--dry-run", action="store_true")

    operator = subparsers.add_parser("operator", help="Operator governance commands")
    operator_sub = operator.add_subparsers(dest="operator_command", required=True)
    operator_sub.add_parser("status", help="Inspect runtime posture")
    inspect = operator_sub.add_parser("inspect", help="Inspect a runtime target")
    inspect.add_argument("target", nargs="?", default="default")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "author" and args.author_command == "init-card":
        print(f"Scaffold placeholder for card: {args.name}")
        return 0

    if args.command == "author" and args.author_command == "validate-card":
        path = Path(args.path)
        if path.exists():
            print(f"Card manifest path exists: {path}")
            return 0
        print(f"Card manifest path not found: {path}")
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
