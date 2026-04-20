from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from math import floor
from pathlib import Path
import statistics
from typing import Any


@dataclass(frozen=True)
class DailyRow:
    symbol: str
    date: str
    close: float
    timesfm_score: float | None
    timesfm_pred_return: float | None
    timesfm_pred_price: float | None


@dataclass(frozen=True)
class Observation:
    symbol: str
    date: str
    future_return_1d: float
    scores: dict[str, float]


BASELINES = (
    "last_return",
    "momentum_5_20",
    "simple_reversal",
    "moving_average_slope",
    "simple_volatility_proxy",
)
TIMESFM_SCORE_NAME = "timesfm"
REQUIRED_COLUMNS = {"date", "symbol", "close"}
OPTIONAL_SCORE_COLUMNS = ("timesfm_score", "timesfm_pred_return", "timesfm_pred_price")


class TimesFMFirstRunError(RuntimeError):
    pass


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return float(text)


def load_daily_rows(path: Path) -> list[DailyRow]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise TimesFMFirstRunError(f"CSV has no header: {path}")
        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            raise TimesFMFirstRunError(
                f"CSV missing required columns: {', '.join(sorted(missing))}"
            )
        if not any(col in reader.fieldnames for col in OPTIONAL_SCORE_COLUMNS):
            raise TimesFMFirstRunError(
                "CSV needs one of timesfm_score, timesfm_pred_return, or timesfm_pred_price"
            )

        rows: list[DailyRow] = []
        for raw in reader:
            rows.append(
                DailyRow(
                    symbol=raw["symbol"].strip(),
                    date=raw["date"].strip(),
                    close=float(raw["close"]),
                    timesfm_score=_safe_float(raw.get("timesfm_score")),
                    timesfm_pred_return=_safe_float(raw.get("timesfm_pred_return")),
                    timesfm_pred_price=_safe_float(raw.get("timesfm_pred_price")),
                )
            )
    rows.sort(key=lambda item: (item.symbol, item.date))
    return rows


def _rank(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j][1] == ordered[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[ordered[k][0]] = avg_rank
        i = j
    return ranks


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    centered_x = [x - mean_x for x in xs]
    centered_y = [y - mean_y for y in ys]
    denom_x = sum(x * x for x in centered_x) ** 0.5
    denom_y = sum(y * y for y in centered_y) ** 0.5
    if denom_x == 0 or denom_y == 0:
        return 0.0
    return sum(x * y for x, y in zip(centered_x, centered_y)) / (denom_x * denom_y)


def _spearman(xs: list[float], ys: list[float]) -> float:
    return _corr(_rank(xs), _rank(ys))


def _split_slices(dates: list[str], slice_count: int) -> list[list[str]]:
    if len(dates) < slice_count:
        raise TimesFMFirstRunError(
            f"Need at least {slice_count} evaluation dates, got {len(dates)}"
        )
    chunked: list[list[str]] = []
    for i in range(slice_count):
        start = floor(i * len(dates) / slice_count)
        end = floor((i + 1) * len(dates) / slice_count)
        chunk = dates[start:end]
        if not chunk:
            raise TimesFMFirstRunError("Unable to form non-empty walk-forward slices")
        chunked.append(chunk)
    return chunked


def build_observations(rows: list[DailyRow], universe_min_symbols: int) -> tuple[list[Observation], list[str]]:
    by_symbol: dict[str, list[DailyRow]] = {}
    for row in rows:
        by_symbol.setdefault(row.symbol, []).append(row)

    observations: list[Observation] = []
    for symbol, series in by_symbol.items():
        series = sorted(series, key=lambda item: item.date)
        closes = [item.close for item in series]
        returns: list[float | None] = [None]
        for idx in range(1, len(series)):
            returns.append(closes[idx] / closes[idx - 1] - 1.0)

        for idx in range(20, len(series) - 1):
            row = series[idx]
            last_return = returns[idx]
            if last_return is None:
                continue
            ma5 = statistics.fmean(closes[idx - 4 : idx + 1])
            ma20 = statistics.fmean(closes[idx - 19 : idx + 1])
            vol5 = statistics.pstdev([value for value in returns[idx - 4 : idx + 1] if value is not None])
            momentum_5 = closes[idx] / closes[idx - 5] - 1.0
            momentum_20 = closes[idx] / closes[idx - 20] - 1.0
            next_close = series[idx + 1].close
            future_return = next_close / closes[idx] - 1.0

            timesfm = row.timesfm_score
            if timesfm is None and row.timesfm_pred_return is not None:
                timesfm = row.timesfm_pred_return
            if timesfm is None and row.timesfm_pred_price is not None:
                timesfm = row.timesfm_pred_price / row.close - 1.0
            if timesfm is None:
                continue

            observations.append(
                Observation(
                    symbol=symbol,
                    date=row.date,
                    future_return_1d=future_return,
                    scores={
                        TIMESFM_SCORE_NAME: timesfm,
                        "last_return": last_return,
                        "momentum_5_20": momentum_5 - momentum_20,
                        "simple_reversal": -last_return,
                        "moving_average_slope": ma5 / ma20 - 1.0,
                        "simple_volatility_proxy": -vol5,
                    },
                )
            )

    by_date: dict[str, list[Observation]] = {}
    for obs in observations:
        by_date.setdefault(obs.date, []).append(obs)
    if not by_date:
        raise TimesFMFirstRunError("No usable observations after lookback and future-return alignment")

    shared_symbols = None
    for date in sorted(by_date):
        symbols = {obs.symbol for obs in by_date[date]}
        shared_symbols = symbols if shared_symbols is None else shared_symbols & symbols
    shared_symbols = shared_symbols or set()
    if len(shared_symbols) < universe_min_symbols:
        raise TimesFMFirstRunError(
            f"Fixed-universe intersection too small: {len(shared_symbols)} symbol(s)"
        )

    filtered = [obs for obs in observations if obs.symbol in shared_symbols]
    dates = sorted({obs.date for obs in filtered})
    return filtered, dates


def _top_group_size(n: int, top_k: int | None) -> int:
    if top_k is not None:
        return max(1, min(top_k, n // 2 if n > 1 else 1))
    return max(1, n // 3)


def evaluate_strategy(
    observations: list[Observation],
    dates: list[str],
    strategy: str,
    slice_count: int,
    top_k: int | None,
    turnover_cost_bps: float,
) -> dict[str, Any]:
    by_date: dict[str, list[Observation]] = {}
    for obs in observations:
        by_date.setdefault(obs.date, []).append(obs)

    slices = _split_slices(dates, slice_count)
    slice_results: list[dict[str, Any]] = []

    for idx, slice_dates in enumerate(slices, start=1):
        rank_ics: list[float] = []
        spreads: list[float] = []
        top_positive = 0
        ordering_hits = 0
        prev_top: set[str] | None = None
        turnover_values: list[float] = []

        for date in slice_dates:
            day_rows = sorted(by_date[date], key=lambda item: item.scores[strategy], reverse=True)
            top_n = _top_group_size(len(day_rows), top_k)
            bottom = day_rows[-top_n:]
            top = day_rows[:top_n]
            middle_start = max(0, (len(day_rows) - top_n) // 2)
            middle = day_rows[middle_start : middle_start + top_n]

            score_values = [row.scores[strategy] for row in day_rows]
            future_values = [row.future_return_1d for row in day_rows]
            rank_ics.append(_spearman(score_values, future_values))

            top_return = statistics.fmean(row.future_return_1d for row in top)
            middle_return = statistics.fmean(row.future_return_1d for row in middle)
            bottom_return = statistics.fmean(row.future_return_1d for row in bottom)
            spreads.append(top_return - bottom_return)
            top_positive += 1 if top_return > 0 else 0
            ordering_hits += 1 if top_return >= middle_return >= bottom_return else 0

            top_symbols = {row.symbol for row in top}
            if prev_top is not None:
                turnover_values.append(len(top_symbols.symmetric_difference(prev_top)) / max(len(top_symbols), 1))
            prev_top = top_symbols

        mean_turnover = statistics.fmean(turnover_values) if turnover_values else 0.0
        mean_spread = statistics.fmean(spreads)
        friction_penalty = mean_turnover * (turnover_cost_bps / 10000.0)
        slice_results.append(
            {
                "slice_id": idx,
                "date_range": {"start": slice_dates[0], "end": slice_dates[-1]},
                "observations": len(slice_dates),
                "rank_ic": statistics.fmean(rank_ics),
                "top_bucket_hit_rate": top_positive / len(slice_dates),
                "ordering_rate": ordering_hits / len(slice_dates),
                "top_minus_bottom_spread": mean_spread,
                "mean_turnover": mean_turnover,
                "friction_aware_score": mean_spread - friction_penalty,
            }
        )

    mean_rank_ic = statistics.fmean(item["rank_ic"] for item in slice_results)
    mean_spread = statistics.fmean(item["top_minus_bottom_spread"] for item in slice_results)
    mean_friction = statistics.fmean(item["friction_aware_score"] for item in slice_results)
    return {
        "strategy": strategy,
        "slice_results": slice_results,
        "summary": {
            "rank_ic": mean_rank_ic,
            "top_bucket_hit_rate": statistics.fmean(item["top_bucket_hit_rate"] for item in slice_results),
            "ordering_rate": statistics.fmean(item["ordering_rate"] for item in slice_results),
            "top_minus_bottom_spread": mean_spread,
            "friction_aware_score": mean_friction,
        },
    }


def choose_verdict(strategy_results: dict[str, dict[str, Any]]) -> str:
    timesfm = strategy_results[TIMESFM_SCORE_NAME]["summary"]
    baselines = {name: payload["summary"] for name, payload in strategy_results.items() if name != TIMESFM_SCORE_NAME}
    strongest = max(baselines.values(), key=lambda item: item["friction_aware_score"])

    positive_slices = sum(
        1
        for item in strategy_results[TIMESFM_SCORE_NAME]["slice_results"]
        if item["top_minus_bottom_spread"] > 0 and item["friction_aware_score"] > 0
    )

    if (
        timesfm["rank_ic"] > strongest["rank_ic"]
        and timesfm["friction_aware_score"] > strongest["friction_aware_score"]
        and positive_slices >= 2
    ):
        return "PROMISING"
    if timesfm["friction_aware_score"] > 0 and timesfm["top_minus_bottom_spread"] > 0:
        return "HOLD"
    if timesfm["rank_ic"] > 0 or timesfm["top_minus_bottom_spread"] > 0:
        return "ITERATE"
    return "KILL"


def build_receipt_payload(
    *,
    input_path: Path,
    observations: list[Observation],
    dates: list[str],
    strategy_results: dict[str, dict[str, Any]],
    slice_count: int,
    top_k: int | None,
    turnover_cost_bps: float,
) -> dict[str, Any]:
    verdict = choose_verdict(strategy_results)
    timesfm_summary = strategy_results[TIMESFM_SCORE_NAME]["summary"]
    strongest_baseline_name, strongest_baseline = max(
        (
            (name, payload["summary"])
            for name, payload in strategy_results.items()
            if name != TIMESFM_SCORE_NAME
        ),
        key=lambda item: item[1]["friction_aware_score"],
    )
    return {
        "recorded_at": datetime.now(UTC).isoformat(),
        "input_path": str(input_path.resolve()),
        "family_id": "timesfm_regime_rank_assist",
        "variant_id": "timesfm_bucket_baseline_daily_30m",
        "verifier_id": "timesfm_regime_rank_assist_v1_bucket_baseline",
        "verdict": verdict,
        "topology": "unchanged",
        "input_contract": {
            "required_columns": ["date", "symbol", "close"],
            "timesfm_columns": list(OPTIONAL_SCORE_COLUMNS),
            "fixed_universe_symbols": sorted({obs.symbol for obs in observations}),
            "evaluation_dates": {"start": dates[0], "end": dates[-1], "count": len(dates)},
            "slice_count": slice_count,
            "top_k": top_k,
            "turnover_cost_bps": turnover_cost_bps,
        },
        "baselines_run": list(BASELINES),
        "score_mappings_run": [TIMESFM_SCORE_NAME],
        "strategy_results": strategy_results,
        "interpretation": {
            "strongest_trivial_baseline": strongest_baseline_name,
            "timesfm_vs_strongest": {
                "rank_ic_delta": timesfm_summary["rank_ic"] - strongest_baseline["rank_ic"],
                "spread_delta": timesfm_summary["top_minus_bottom_spread"] - strongest_baseline["top_minus_bottom_spread"],
                "friction_delta": timesfm_summary["friction_aware_score"] - strongest_baseline["friction_aware_score"],
            },
        },
    }


def render_markdown_receipt(payload: dict[str, Any]) -> str:
    timesfm = payload["strategy_results"][TIMESFM_SCORE_NAME]["summary"]
    strongest_name = payload["interpretation"]["strongest_trivial_baseline"]
    strongest = payload["strategy_results"][strongest_name]["summary"]
    date_window = payload["input_contract"]["evaluation_dates"]
    symbols = payload["input_contract"]["fixed_universe_symbols"]
    return "\n".join(
        [
            "# Result receipt — TimesFM v1 bucket baseline",
            "",
            f"- recorded: {payload['recorded_at']}",
            f"- family_id: `{payload['family_id']}`",
            f"- variant_id: `{payload['variant_id']}`",
            f"- verifier_id: `{payload['verifier_id']}`",
            f"- verdict: `{payload['verdict']}`",
            f"- topology: {payload['topology']}",
            "",
            "## Universe rule",
            f"- fixed-universe symbols ({len(symbols)}): {', '.join(symbols)}",
            f"- input path: `{payload['input_path']}`",
            "",
            "## Date range / walk-forward slices",
            f"- evaluation dates: {date_window['start']} -> {date_window['end']} ({date_window['count']} sessions)",
            f"- slice count: {payload['input_contract']['slice_count']}",
            "",
            "## Baselines run",
            *[f"- {name}" for name in payload["baselines_run"]],
            "",
            "## Score mappings run",
            "- TimesFM score resolved from one of: timesfm_score / timesfm_pred_return / timesfm_pred_price",
            "",
            "## Decision-grade metrics",
            f"- TimesFM rank IC: {timesfm['rank_ic']:.4f}",
            f"- TimesFM top bucket hit rate: {timesfm['top_bucket_hit_rate']:.4f}",
            f"- TimesFM top-minus-bottom spread: {timesfm['top_minus_bottom_spread']:.6f}",
            f"- TimesFM friction-aware score: {timesfm['friction_aware_score']:.6f}",
            f"- strongest trivial baseline: {strongest_name}",
            f"- strongest baseline rank IC: {strongest['rank_ic']:.4f}",
            f"- strongest baseline top-minus-bottom spread: {strongest['top_minus_bottom_spread']:.6f}",
            f"- strongest baseline friction-aware score: {strongest['friction_aware_score']:.6f}",
            "",
            "## Interpretation",
            (
                "This runnable substrate now computes the bounded first-pass benchmark honestly from a daily cross-sectional CSV. "
                "Result quality still depends on the input dataset; this receipt does not imply live-sim or card activation."
            ),
            "",
            "## What this proves",
            "- the TimesFM first-run lane now has an executable local substrate",
            "- the lane can emit a bounded receipt with fixed-universe, slice, baseline, and friction-aware metrics",
            "",
            "## What this does not prove",
            "- no live-readiness claim",
            "- no intraday edge claim",
            "- no automatic promotion to an active card/deck",
            "",
            "## Next governed move",
            "- run the same tool on a real fixed-universe daily dataset and judge PROMISING / HOLD / ITERATE / KILL from the resulting receipt",
        ]
    )


def run_first_pass(
    input_path: Path,
    *,
    slice_count: int,
    top_k: int | None,
    turnover_cost_bps: float,
    universe_min_symbols: int,
) -> dict[str, Any]:
    rows = load_daily_rows(input_path)
    observations, dates = build_observations(rows, universe_min_symbols=universe_min_symbols)
    strategy_results = {
        name: evaluate_strategy(
            observations,
            dates,
            name,
            slice_count=slice_count,
            top_k=top_k,
            turnover_cost_bps=turnover_cost_bps,
        )
        for name in (TIMESFM_SCORE_NAME, *BASELINES)
    }
    payload = build_receipt_payload(
        input_path=input_path,
        observations=observations,
        dates=dates,
        strategy_results=strategy_results,
        slice_count=slice_count,
        top_k=top_k,
        turnover_cost_bps=turnover_cost_bps,
    )
    payload["markdown_receipt"] = render_markdown_receipt(payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="steamer-card-engine-timesfm-first-run",
        description="Execute the bounded TimesFM first-pass benchmark from a daily cross-sectional CSV.",
    )
    parser.add_argument("input_path", help="CSV path with date,symbol,close and one TimesFM score column")
    parser.add_argument("--receipt-md", help="Optional markdown receipt output path")
    parser.add_argument("--receipt-json", help="Optional JSON receipt output path")
    parser.add_argument("--slice-count", type=int, default=3)
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--turnover-cost-bps", type=float, default=10.0)
    parser.add_argument("--universe-min-symbols", type=int, default=3)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = run_first_pass(
        Path(args.input_path),
        slice_count=args.slice_count,
        top_k=args.top_k,
        turnover_cost_bps=args.turnover_cost_bps,
        universe_min_symbols=args.universe_min_symbols,
    )

    if args.receipt_json:
        Path(args.receipt_json).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
    if args.receipt_md:
        Path(args.receipt_md).write_text(payload["markdown_receipt"], encoding="utf-8")

    if args.as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        print(payload["markdown_receipt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
