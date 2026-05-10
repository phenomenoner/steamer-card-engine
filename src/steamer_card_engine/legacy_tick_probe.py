from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean
from typing import Any

from .legacy_equivalence import DEFAULT_DATA_ROOT, LegacyEquivalenceError, resolve_output_dir


PROBE_FIELDS = ("px", "open_px", "max_seen", "min_seen")


def _tick_ts(row: dict[str, Any]) -> float | None:
    # Legacy state `now_ts` is built from exchange `time` microseconds, not
    # recorder receive time. Using ws_received_time creates false mismatches.
    if isinstance(row.get("time"), (int, float)):
        value = float(row["time"])
        return value / 1_000_000 if value > 1_000_000_000_000 else value
    if isinstance(row.get("ws_received_time"), (int, float)):
        return float(row["ws_received_time"])
    return None


def load_tick_series(ticks_path: Path) -> dict[str, dict[str, list[float]]]:
    series: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"ts": [], "price": []})
    with ticks_path.open("r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            row = json.loads(line)
            symbol = str(row.get("symbol") or "")
            # Legacy only updates price-path state for market-open/continuous ticks;
            # pre-open trial ticks are recorded but should not seed open/high/low.
            if "isOpen" not in row and "isContinuous" not in row:
                continue
            price = row.get("price")
            ts = _tick_ts(row)
            if not symbol or ts is None or not isinstance(price, (int, float)):
                continue
            bucket = series[symbol]
            bucket["ts"].append(float(ts))
            bucket["price"].append(float(price))
    for bucket in series.values():
        pairs = sorted(zip(bucket["ts"], bucket["price"]))
        bucket["ts"] = [item[0] for item in pairs]
        bucket["price"] = [item[1] for item in pairs]
    return dict(series)


def reconstruct_at(series: dict[str, list[float]], ts: float) -> dict[str, Any] | None:
    right_idx = bisect_right(series["ts"], ts) - 1
    if right_idx < 0:
        return None
    left_idx = bisect_left(series["ts"], ts)
    right_prices = series["price"][: right_idx + 1]
    before_prices = series["price"][:left_idx]
    same_ts_prices = series["price"][left_idx : right_idx + 1]
    return {
        "px": right_prices[-1],
        "open_px": right_prices[0],
        "max_seen": max(right_prices),
        "min_seen": min(right_prices),
        "same_ts_prices": same_ts_prices,
        "before_same_ts": {
            "max_seen": max(before_prices) if before_prices else None,
            "min_seen": min(before_prices) if before_prices else None,
        },
    }


def _is_timestamp_ambiguous_match(field: str, legacy_value: float, reconstructed: dict[str, Any], tolerance: float) -> bool:
    same_ts_prices = reconstructed.get("same_ts_prices") or []
    if len(same_ts_prices) <= 1:
        return False
    if field == "px":
        return any(abs(legacy_value - float(price)) <= tolerance for price in same_ts_prices)
    if field in {"max_seen", "min_seen"}:
        before_value = (reconstructed.get("before_same_ts") or {}).get(field)
        final_value = reconstructed.get(field)
        if before_value is None or final_value is None:
            return False
        low = min(float(before_value), float(final_value), *[float(price) for price in same_ts_prices])
        high = max(float(before_value), float(final_value), *[float(price) for price in same_ts_prices])
        return (low - tolerance) <= legacy_value <= (high + tolerance)
    return False


def iter_sampled_decisions(path: Path, gate: str, max_samples: int) -> list[tuple[int, dict[str, Any]]]:
    matches: list[tuple[int, dict[str, Any]]] = []
    total = 0
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("gate") != gate:
                continue
            total += 1
            if len(matches) < max_samples:
                matches.append((line_no, row))
            else:
                # Deterministic reservoir-ish replacement without randomness.
                interval = max(1, total // max_samples)
                if total % interval == 0:
                    matches[(total // interval) % max_samples] = (line_no, row)
    return sorted(matches, key=lambda item: item[0])


def probe_session(
    *,
    data_root: Path,
    machine: str,
    date: str,
    gate: str,
    max_samples: int,
    tolerance: float,
) -> dict[str, Any]:
    session_dir = data_root / machine / date
    ticks_path = session_dir / "ticks.jsonl"
    decisions_path = session_dir / "decisions.jsonl"
    if not ticks_path.exists() or not decisions_path.exists():
        raise LegacyEquivalenceError(f"missing ticks/decisions under {session_dir}")

    tick_series = load_tick_series(ticks_path)
    sampled = iter_sampled_decisions(decisions_path, gate, max_samples)
    if not sampled:
        raise LegacyEquivalenceError(f"no sampled decisions for gate {gate} in {decisions_path}")

    field_abs_errors: dict[str, list[float]] = {field: [] for field in PROBE_FIELDS}
    field_mismatches: dict[str, int] = {field: 0 for field in PROBE_FIELDS}
    field_timestamp_ambiguous: dict[str, int] = {field: 0 for field in PROBE_FIELDS}
    missing_symbol = 0
    before_first_tick = 0
    samples: list[dict[str, Any]] = []

    for line_no, row in sampled:
        state = row.get("state") or {}
        symbol = str(row.get("symbol") or state.get("symbol") or "")
        now_ts = state.get("now_ts")
        if symbol not in tick_series:
            missing_symbol += 1
            continue
        if not isinstance(now_ts, (int, float)):
            before_first_tick += 1
            continue
        reconstructed = reconstruct_at(tick_series[symbol], float(now_ts))
        if reconstructed is None:
            before_first_tick += 1
            continue
        sample_diff = {
            "line_no": line_no,
            "symbol": symbol,
            "now_ts": now_ts,
            "now_time": state.get("now_time"),
            "fields": {},
        }
        has_mismatch = False
        for field in PROBE_FIELDS:
            legacy_value = state.get(field)
            candidate_value = reconstructed.get(field)
            if not isinstance(legacy_value, (int, float)) or candidate_value is None:
                continue
            error = abs(float(legacy_value) - float(candidate_value))
            field_abs_errors[field].append(error)
            mismatch = error > tolerance
            ambiguous = False
            if mismatch and _is_timestamp_ambiguous_match(field, float(legacy_value), reconstructed, tolerance):
                ambiguous = True
                mismatch = False
                field_timestamp_ambiguous[field] += 1
            if mismatch:
                field_mismatches[field] += 1
                has_mismatch = True
            sample_diff["fields"][field] = {
                "legacy": legacy_value,
                "reconstructed": candidate_value,
                "abs_error": error,
                "mismatch": mismatch,
                "timestamp_ambiguous": ambiguous,
            }
        if has_mismatch and len(samples) < 25:
            samples.append(sample_diff)

    compared = {field: len(errors) for field, errors in field_abs_errors.items()}
    error_summary = {
        field: {
            "compared": len(errors),
            "mean_abs_error": mean(errors) if errors else None,
            "max_abs_error": max(errors) if errors else None,
            "mismatches": field_mismatches[field],
            "timestamp_ambiguous_matches": field_timestamp_ambiguous[field],
            "match_rate": 1.0 - (field_mismatches[field] / len(errors) if errors else 0.0),
        }
        for field, errors in field_abs_errors.items()
    }
    all_compared = sum(compared.values())
    all_mismatches = sum(field_mismatches.values())
    verdict = "PASS_FEASIBLE" if all_compared and all_mismatches == 0 else "NEEDS_RECONSTRUCTION_WORK"
    return {
        "kind": "steamer_card_engine.legacy_tick_probe.v1",
        "verdict": verdict,
        "data_root": str(data_root),
        "machine": machine,
        "date": date,
        "gate": gate,
        "sampled_decisions": len(sampled),
        "symbols_with_ticks": len(tick_series),
        "missing_symbol_samples": missing_symbol,
        "before_first_tick_samples": before_first_tick,
        "tolerance": tolerance,
        "field_summary": error_summary,
        "mismatch_samples": samples,
    }


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Legacy tick reconstruction feasibility probe",
        "",
        f"## Verdict\n{summary['verdict']}",
        "",
        f"- dataset: `{summary['machine']}/{summary['date']}`",
        f"- gate: `{summary['gate']}`",
        f"- sampled decisions: {summary['sampled_decisions']}",
        f"- symbols with ticks: {summary['symbols_with_ticks']}",
        f"- tolerance: {summary['tolerance']}",
        "",
        "## Field reconstruction",
        "",
        "| field | compared | mismatches | match rate | max abs error | mean abs error |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for field, stats in summary["field_summary"].items():
        lines.append(
            f"| {field} | {stats['compared']} | {stats['mismatches']} | {stats['match_rate']:.4f} | "
            f"{stats['max_abs_error']} | {stats['mean_abs_error']} |"
        )
    lines.extend([
        "",
        "## Interpretation",
        "This probe only tests whether core price-path fields can be reconstructed from ticks at historical decision timestamps.",
        "It does not yet reconstruct EMA, slope, zigzag, VCP, or risk/order state.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root).resolve()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = probe_session(
        data_root=data_root,
        machine=args.machine,
        date=args.date,
        gate=args.gate,
        max_samples=args.max_samples,
        tolerance=args.tolerance,
    )
    summary_path = output_dir / "tick_probe_summary.json"
    report_path = output_dir / "tick_probe_report.md"
    summary["summary_path"] = str(summary_path)
    summary["report_path"] = str(report_path)
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({"verdict": summary["verdict"], "summary_path": str(summary_path), "report_path": str(report_path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe whether legacy decisions can be reconstructed from recorded ticks.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--machine", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--gate", default="REV_SHORT_AFTER_UP")
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
