from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from steamer_card_engine.timesfm_first_run import OPTIONAL_SCORE_COLUMNS

REQUIRED_CLOSE_COLUMNS = {"date", "symbol", "close"}
REQUIRED_SCORE_KEYS = {"date", "symbol"}
WATCHLIST_DATE_KEYS = ("run_date", "date")


class TimesFMInputBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeRow:
    date: str
    symbol: str
    close: float
    score_column: str
    score_value: float


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise TimesFMInputBridgeError(f"CSV has no header: {path}")
        return list(reader), list(reader.fieldnames)


def _pick_score_column(fieldnames: list[str], requested: str | None) -> str:
    if requested is not None:
        if requested not in fieldnames:
            raise TimesFMInputBridgeError(
                f"Requested score column '{requested}' not present in score CSV"
            )
        return requested
    for candidate in OPTIONAL_SCORE_COLUMNS:
        if candidate in fieldnames:
            return candidate
    raise TimesFMInputBridgeError(
        "Score CSV needs one of timesfm_score, timesfm_pred_return, or timesfm_pred_price"
    )


def _normalize_symbol(value: str) -> str:
    return value.strip()


def _normalize_date(value: str) -> str:
    return value.strip()


def _watchlist_allowed(path: Path | None) -> set[tuple[str, str]] | None:
    if path is None:
        return None
    rows, fieldnames = _read_csv(path)
    if "symbol" not in fieldnames:
        raise TimesFMInputBridgeError("Watchlist CSV missing required column: symbol")
    date_column = next((name for name in WATCHLIST_DATE_KEYS if name in fieldnames), None)
    if date_column is None:
        raise TimesFMInputBridgeError("Watchlist CSV needs run_date or date column")
    allowed: set[tuple[str, str]] = set()
    for row in rows:
        symbol = _normalize_symbol(row["symbol"])
        date = _normalize_date(row[date_column])
        if symbol and date:
            allowed.add((date, symbol))
    return allowed


def build_timesfm_input(
    close_history_path: Path,
    score_path: Path,
    out_path: Path,
    *,
    watchlist_path: Path | None = None,
    score_column: str | None = None,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    close_rows, close_fields = _read_csv(close_history_path)
    score_rows, score_fields = _read_csv(score_path)

    missing_close = REQUIRED_CLOSE_COLUMNS - set(close_fields)
    if missing_close:
        raise TimesFMInputBridgeError(
            f"Close history CSV missing required columns: {', '.join(sorted(missing_close))}"
        )
    missing_score = REQUIRED_SCORE_KEYS - set(score_fields)
    if missing_score:
        raise TimesFMInputBridgeError(
            f"Score CSV missing required columns: {', '.join(sorted(missing_score))}"
        )

    chosen_score = _pick_score_column(score_fields, score_column)
    allowed = _watchlist_allowed(watchlist_path)

    close_map: dict[tuple[str, str], float] = {}
    for row in close_rows:
        date = _normalize_date(row["date"])
        symbol = _normalize_symbol(row["symbol"])
        if not date or not symbol:
            continue
        close_map[(date, symbol)] = float(row["close"])

    bridged: list[BridgeRow] = []
    missing_close_keys: list[tuple[str, str]] = []
    skipped_empty_scores = 0
    skipped_watchlist = 0

    for row in score_rows:
        date = _normalize_date(row["date"])
        symbol = _normalize_symbol(row["symbol"])
        if not date or not symbol:
            continue
        if allowed is not None and (date, symbol) not in allowed:
            skipped_watchlist += 1
            continue
        raw_score = (row.get(chosen_score) or "").strip()
        if not raw_score:
            skipped_empty_scores += 1
            continue
        key = (date, symbol)
        close_value = close_map.get(key)
        if close_value is None:
            missing_close_keys.append(key)
            continue
        bridged.append(
            BridgeRow(
                date=date,
                symbol=symbol,
                close=close_value,
                score_column=chosen_score,
                score_value=float(raw_score),
            )
        )

    if not bridged:
        raise TimesFMInputBridgeError("No bridged rows survived the merge")

    bridged.sort(key=lambda item: (item.date, item.symbol))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "symbol", "close", chosen_score]
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in bridged:
            writer.writerow(
                {
                    "date": row.date,
                    "symbol": row.symbol,
                    "close": f"{row.close:.10g}",
                    chosen_score: f"{row.score_value:.10g}",
                }
            )

    summary = {
        "close_history_path": str(close_history_path),
        "score_path": str(score_path),
        "watchlist_path": str(watchlist_path) if watchlist_path else None,
        "out_path": str(out_path),
        "score_column": chosen_score,
        "rows_written": len(bridged),
        "unique_dates": len({row.date for row in bridged}),
        "unique_symbols": len({row.symbol for row in bridged}),
        "skipped_empty_scores": skipped_empty_scores,
        "skipped_watchlist": skipped_watchlist,
        "missing_close_rows": len(missing_close_keys),
        "missing_close_examples": [
            {"date": date, "symbol": symbol} for date, symbol in missing_close_keys[:10]
        ],
    }
    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steamer-card-engine-timesfm-build-input",
        description="Bridge external TimesFM score CSVs into the bounded first-run input contract.",
    )
    parser.add_argument("--close-history", required=True, help="CSV with date,symbol,close")
    parser.add_argument("--score-csv", required=True, help="CSV with date,symbol and a TimesFM score column")
    parser.add_argument("--watchlist-csv", help="Optional watchlist CSV with run_date/date + symbol")
    parser.add_argument("--score-column", help="Explicit score column to import")
    parser.add_argument("--out", required=True, help="Output CSV path for steamer-card-engine-timesfm-first-run")
    parser.add_argument("--summary-json", help="Optional summary JSON output path")
    parser.add_argument("--json", action="store_true", help="Print summary JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = build_timesfm_input(
        Path(args.close_history),
        Path(args.score_csv),
        Path(args.out),
        watchlist_path=Path(args.watchlist_csv) if args.watchlist_csv else None,
        score_column=args.score_column,
        summary_path=Path(args.summary_json) if args.summary_json else None,
    )
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"wrote {summary['rows_written']} row(s) to {summary['out_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
