from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .runtime_store import import_runtime_files_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain the Steamer dashboard SQLite runtime store.")
    parser.add_argument("--db", required=True, help="Path to runtime.sqlite")
    parser.add_argument("--root", required=True, help="Runtime data root to scan")
    parser.add_argument("--date", action="append", default=[], help="Date to import, repeatable. Defaults to discovery.")
    parser.add_argument("--latest", type=int, default=0, help="Import latest N discovered runtime dates. Ignored when --date is provided.")
    parser.add_argument("--receipt", help="Optional JSON receipt path")
    return parser


def _latest_dates(root: str, limit: int) -> list[str]:
    if limit <= 0:
        return []
    from .runtime_store import _discover_dates

    return [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in _discover_dates(Path(root))[:limit]]


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dates = args.date or _latest_dates(args.root, args.latest)
    receipt = import_runtime_files_once(args.db, args.root, dates=dates or None)
    payload = receipt.__dict__
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if args.receipt:
        path = Path(args.receipt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
