from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import time
import json
from pathlib import Path
from typing import Any, Callable


DEFAULT_DATA_ROOT = Path("/workspace/CC/StrategyExecuter_Steamer-Antigravity/.data")


DEFAULT_GATE_CONFIG: dict[str, Any] = {
    "allow_blind_open": False,
    "sweet_ok": True,
    "enable_zz": True,
    "enable_angle": True,
    "require_recent_high": True,
    # The January 2026 DT3 REV_SHORT_AFTER_UP traces record `now_time_5` before 09:30.
    "market_gate": 5,
    "strong_up_pct": 3.0,
    "strong_up_pct_abs": 5.0,
    "fallback_pct": 1.2,
    "trend_conflict_slope_threshold": 5.0,
    "trend_conflict_override_slope": -15.0,
    # January 2026 legacy traces match the documented >5% profit-buffer semantics
    # for the time-fresh high fallback, not the later local code's >3% expression.
    "honey_sweet_profit_pct": 5.0,
    # VCP compatibility defaults. Older January traces may have used earlier semantics;
    # the verifier reports those divergences rather than hiding them.
    "vcp_min_trend_slope": 10.0,
    "vcp_tightness_pct": 0.35,
    "vcp_breakout_vol_mult": 2.5,
}

SUPPORTED_GATES = {"REV_SHORT_AFTER_UP", "LONG_ONE_VCP"}
DEFAULT_OUTPUT_ROOT = Path("runs/legacy-equivalence")


class LegacyEquivalenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GateDecision:
    enter: bool
    reason: str


def _parse_time(value: Any) -> Any:
    if isinstance(value, time) or value is None:
        return value
    if isinstance(value, str):
        try:
            return time.fromisoformat(value)
        except ValueError:
            return value
    return value


def normalize_state(raw: dict[str, Any]) -> dict[str, Any]:
    state = dict(raw)
    state["now_time"] = _parse_time(state.get("now_time"))
    return state


def rev_short_after_up_card_decision(state: dict[str, Any], cfg: dict[str, Any]) -> GateDecision:
    s = state
    c = cfg
    if s["is_open"] and not c.get("allow_blind_open", False):
        return GateDecision(False, "blocked_blind_open")
    if not s["sweet_ok"]:
        return GateDecision(False, "sweet")

    the_gate = c.get("market_gate", 0)
    now_time = s.get("now_time")
    if isinstance(now_time, time):
        if 3 <= the_gate < 5:
            if now_time < time(9, 15):
                return GateDecision(False, "now_time_3")
        elif 5 <= the_gate:
            if now_time < time(9, 30):
                return GateDecision(False, "now_time_5")

    lock_start = s.get("upper_limit_start_time")
    if the_gate > 3 and lock_start is not None and s.get("now_ts") is not None:
        duration = s["now_ts"] - lock_start
        if duration >= 15 * 60:
            return GateDecision(False, f"upper_limit_lock_15m ({int(duration)}s)")

    up_vs_close_abs = 100.0 * (s["max_seen"] - s["last_close"]) / max(s["last_close"], 1e-9)
    up_vs_close = 100.0 * (s["max_seen"] - s["open_px"]) / max(s["open_px"], 1e-9)
    if (up_vs_close < c["strong_up_pct"]) and (up_vs_close_abs < c["strong_up_pct_abs"]):
        return GateDecision(False, "not_strong_up")

    has_price_high = s["new_high_recent"]
    time_since_high = s["now_ts"] - s.get("last_qualified_high_ts", 0)
    has_time_high = time_since_high < 1200
    honey_sweet_profit_pct = c.get("honey_sweet_profit_pct", 5.0)
    is_honey_sweet_profit = (
        100.0 * (s["px"] - s["last_close"]) / max(s["last_close"], 1e-9)
    ) > honey_sweet_profit_pct
    if c["require_recent_high"]:
        if not (has_price_high or (has_time_high and is_honey_sweet_profit)):
            return GateDecision(False, "no_recent_high")

    if c["enable_zz"] and s["zz_trend"] >= 0:
        return GateDecision(False, "zz_not_down")
    if c["enable_angle"] and not s["slope_down_ok"]:
        return GateDecision(False, "angle")
    if s["px"] > s["max_seen"] * (1.0 - c["fallback_pct"] / 100.0):
        return GateDecision(False, "too_shallow")
    if s["price_ema"] is None:
        return GateDecision(False, "none_ema")
    if not (s["px"] < s["price_ema"]):
        return GateDecision(False, "above_ema")

    if the_gate >= 5:
        strong_trend_thr = c.get("trend_conflict_slope_threshold", 5.0)
        override_thr = c.get("trend_conflict_override_slope", -15.0)
        sl1 = s["slope"] if s["slope"] is not None else 0
        sl2 = s["slope_2"] if s["slope_2"] is not None else 0
        sl3 = s["slope_3"] if s["slope_3"] is not None else 0
        if (sl2 > strong_trend_thr) or (sl3 > strong_trend_thr):
            if sl1 > override_thr:
                return GateDecision(
                    False,
                    f"trend_conflict: sl2/3({sl2}/{sl3})> {strong_trend_thr} & sl1({sl1}) > {override_thr}",
                )

    return GateDecision(True, "enter_rev_short")


def long_one_vcp_card_decision(state: dict[str, Any], cfg: dict[str, Any]) -> GateDecision:
    s = state
    c = cfg
    if s["is_open"] and not c.get("allow_blind_open", False):
        return GateDecision(False, "blocked_blind_open")
    if not s["sweet_ok"]:
        return GateDecision(False, "sweet")

    min_slope = c.get("vcp_min_trend_slope", 10.0)
    sl3 = s.get("slope_3")
    if sl3 is None:
        return GateDecision(False, f"trend_not_ready: slope_3 None (min_slope={min_slope})")
    if sl3 < min_slope:
        return GateDecision(False, f"trend_not_strong_enough: slope_3 {sl3} < {min_slope}")

    ema = s.get("price_ema")
    px = s["px"]
    if (ema is not None) and (px < ema):
        return GateDecision(False, f"price_below_ema: {px} < {ema}")

    is_tight = s.get("vcp_is_tight", False)
    range_pct = s.get("vcp_range_pct", 999.0)
    tight_thr = c.get("vcp_tightness_pct", 0.35)
    if (not is_tight) and (range_pct > tight_thr):
        return GateDecision(False, f"consolidation_too_loose: range_pct {range_pct:.3f}% > {tight_thr}%")

    if not s.get("vcp_vol_dryup_ok", False):
        return GateDecision(False, "no_vol_dryup_context")

    box_high = s.get("vcp_box_high", 999999.0)
    if px <= box_high:
        return GateDecision(False, f"not_breakout: {px} <= {box_high}")

    breakout_vol_mult = c.get("vcp_breakout_vol_mult", 2.5)
    cur_vol_ratio = s.get("vcp_current_vol_ratio", 0.0)
    if cur_vol_ratio < breakout_vol_mult:
        return GateDecision(False, f"no_vol_spike: ratio {cur_vol_ratio:.2f} < {breakout_vol_mult}")

    return GateDecision(True, "enter_long_vcp_breakout")


GATE_EVALUATORS: dict[str, Callable[[dict[str, Any], dict[str, Any]], GateDecision]] = {
    "REV_SHORT_AFTER_UP": rev_short_after_up_card_decision,
    "LONG_ONE_VCP": long_one_vcp_card_decision,
}


def load_config(path: Path | None) -> dict[str, Any]:
    cfg = dict(DEFAULT_GATE_CONFIG)
    if path is None:
        return cfg
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise LegacyEquivalenceError("config JSON must be an object")
    cfg.update(payload)
    return cfg


def iter_decision_files(data_root: Path, gates: set[str]) -> list[Path]:
    files = sorted(data_root.glob("*/20*/decisions.jsonl"))
    selected: list[Path] = []
    for path in files:
        if path.stat().st_size == 0:
            continue
        # Cheap sniff: include only if at least one requested gate appears.
        include = False
        with path.open("r", encoding="utf-8") as file:
            for index, line in enumerate(file):
                if index > 5000 and include is False:
                    break
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("gate") in gates:
                    include = True
                    break
        if include:
            selected.append(path)
    return selected


def _rel_dataset(path: Path, data_root: Path) -> tuple[str, str]:
    try:
        rel = path.relative_to(data_root)
    except ValueError:
        return "external", path.parent.name or "unknown-date"
    if len(rel.parts) < 2:
        return "unknown", "unknown-date"
    return rel.parts[0], rel.parts[1]


def resolve_output_dir(raw_output_dir: str) -> Path:
    requested = Path(raw_output_dir)
    if requested.is_absolute():
        raise LegacyEquivalenceError("--output-dir must be relative and stay under runs/legacy-equivalence")
    normalized = (Path.cwd() / requested).resolve()
    allowed_root = (Path.cwd() / DEFAULT_OUTPUT_ROOT).resolve()
    if normalized != allowed_root and allowed_root not in normalized.parents:
        raise LegacyEquivalenceError("--output-dir must stay under runs/legacy-equivalence")
    return normalized


def compare_file(
    path: Path,
    *,
    data_root: Path,
    gates: set[str],
    cfg: dict[str, Any],
    max_mismatch_samples: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    machine, session_date = _rel_dataset(path, data_root)
    by_gate: dict[str, dict[str, Any]] = {}
    samples: list[dict[str, Any]] = []

    for line_no, line in enumerate(path.open("r", encoding="utf-8"), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        gate = row.get("gate")
        if gate not in gates:
            continue
        evaluator = GATE_EVALUATORS[gate]
        bucket = by_gate.setdefault(
            gate,
            {
                "rows": 0,
                "enter_mismatches": 0,
                "reason_mismatches": 0,
                "legacy_enter_true": 0,
                "candidate_enter_true": 0,
                "legacy_reasons": Counter(),
                "candidate_reasons": Counter(),
                "first_mismatch": None,
            },
        )
        bucket["rows"] += 1
        legacy_enter = bool(row.get("enter"))
        legacy_reason = str(row.get("reason"))
        state = normalize_state(row.get("state") or {})
        candidate = evaluator(state, cfg)
        if legacy_enter:
            bucket["legacy_enter_true"] += 1
        if candidate.enter:
            bucket["candidate_enter_true"] += 1
        bucket["legacy_reasons"][legacy_reason] += 1
        bucket["candidate_reasons"][candidate.reason] += 1

        enter_match = legacy_enter == candidate.enter
        reason_match = legacy_reason == candidate.reason
        if not enter_match:
            bucket["enter_mismatches"] += 1
        if not reason_match:
            bucket["reason_mismatches"] += 1
        if not (enter_match and reason_match):
            sample = {
                "machine": machine,
                "date": session_date,
                "gate": gate,
                "line_no": line_no,
                "symbol": row.get("symbol"),
                "legacy_enter": legacy_enter,
                "candidate_enter": candidate.enter,
                "legacy_reason": legacy_reason,
                "candidate_reason": candidate.reason,
                "state_now_time": row.get("state", {}).get("now_time"),
                "state_now_ts": row.get("state", {}).get("now_ts"),
            }
            if bucket["first_mismatch"] is None:
                bucket["first_mismatch"] = sample
            if len(samples) < max_mismatch_samples:
                samples.append(sample)

    serializable_by_gate: dict[str, Any] = {}
    for gate, bucket in by_gate.items():
        rows = bucket["rows"]
        serializable_by_gate[gate] = {
            "rows": rows,
            "enter_mismatches": bucket["enter_mismatches"],
            "reason_mismatches": bucket["reason_mismatches"],
            "enter_match_rate": 1.0 - (bucket["enter_mismatches"] / rows if rows else 0.0),
            "reason_match_rate": 1.0 - (bucket["reason_mismatches"] / rows if rows else 0.0),
            "legacy_enter_true": bucket["legacy_enter_true"],
            "candidate_enter_true": bucket["candidate_enter_true"],
            "legacy_reasons_top10": dict(bucket["legacy_reasons"].most_common(10)),
            "candidate_reasons_top10": dict(bucket["candidate_reasons"].most_common(10)),
            "first_mismatch": bucket["first_mismatch"],
        }

    return {
        "machine": machine,
        "date": session_date,
        "source": str(path),
        "gates": serializable_by_gate,
    }, samples


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Legacy decision trace equivalence report",
        "",
        f"Machine summary: `{summary['summary_path']}`",
        f"Mismatch samples: `{summary['mismatch_samples_path']}`",
        "",
        "## Verdict",
        summary["verdict"],
        "",
        "## Scope",
        f"- data_root: `{summary['data_root']}`",
        f"- gates: {', '.join(summary['gates'])}",
        f"- datasets: {summary['dataset_count']}",
        "- Equality target: decision trace (`enter`, `reason`) from embedded legacy `state`; not PnL/fill/execution equivalence.",
        "",
        "## Aggregate",
        "",
        "| gate | rows | enter mismatches | reason mismatches | enter match | reason match |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for gate, agg in summary["aggregate_by_gate"].items():
        lines.append(
            f"| {gate} | {agg['rows']} | {agg['enter_mismatches']} | {agg['reason_mismatches']} | "
            f"{agg['enter_match_rate']:.6f} | {agg['reason_match_rate']:.6f} |"
        )
    lines.extend(["", "## Per dataset", ""])
    for dataset in summary["datasets"]:
        for gate, stats in dataset["gates"].items():
            lines.append(
                f"- `{dataset['machine']}/{dataset['date']}` `{gate}`: rows={stats['rows']}, "
                f"enter_mismatches={stats['enter_mismatches']}, reason_mismatches={stats['reason_mismatches']}, "
                f"enter_match={stats['enter_match_rate']:.6f}, reason_match={stats['reason_match_rate']:.6f}"
            )
    lines.extend([
        "",
        "## Limitations",
        "- The first slice uses compatibility-card gate functions over already-recorded legacy state snapshots.",
        "- It does not reconstruct features from ticks yet; if state fields are absent, that future phase is required.",
        "- VCP January traces may reflect older legacy semantics; divergences are reported, not normalized away.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root).resolve()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_gates = args.gate or ["REV_SHORT_AFTER_UP"]
    gates = {gate.strip() for gate in raw_gates if gate.strip()}
    unknown = gates - SUPPORTED_GATES
    if unknown:
        raise LegacyEquivalenceError(f"unsupported gates: {sorted(unknown)}")
    cfg = load_config(Path(args.config).resolve() if args.config else None)

    if args.decision_file:
        decision_files = [Path(item).resolve() for item in args.decision_file]
    else:
        decision_files = iter_decision_files(data_root, gates)

    datasets: list[dict[str, Any]] = []
    mismatch_samples: list[dict[str, Any]] = []
    aggregate: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "enter_mismatches": 0,
            "reason_mismatches": 0,
            "legacy_enter_true": 0,
            "candidate_enter_true": 0,
        }
    )

    for path in decision_files:
        dataset, samples = compare_file(
            path,
            data_root=data_root,
            gates=gates,
            cfg=cfg,
            max_mismatch_samples=max(0, args.max_mismatch_samples - len(mismatch_samples)),
        )
        if not dataset["gates"]:
            continue
        datasets.append(dataset)
        mismatch_samples.extend(samples)
        for gate, stats in dataset["gates"].items():
            agg = aggregate[gate]
            for key in ["rows", "enter_mismatches", "reason_mismatches", "legacy_enter_true", "candidate_enter_true"]:
                agg[key] += stats[key]

    if not datasets:
        raise LegacyEquivalenceError("no matching decision rows found; refusing to emit a PASS artifact")

    aggregate_by_gate: dict[str, Any] = {}
    verdict = "PASS"
    for gate in sorted(aggregate):
        agg = aggregate[gate]
        rows = agg["rows"]
        agg["enter_match_rate"] = 1.0 - (agg["enter_mismatches"] / rows if rows else 0.0)
        agg["reason_match_rate"] = 1.0 - (agg["reason_mismatches"] / rows if rows else 0.0)
        aggregate_by_gate[gate] = dict(agg)
        if agg["enter_mismatches"] or agg["reason_mismatches"]:
            verdict = "FAIL_NEEDS_COMPATIBILITY_MAPPING"

    summary_path = output_dir / "summary.json"
    mismatch_path = output_dir / "mismatch_samples.jsonl"
    report_path = output_dir / "consistency_report.md"
    config_path = output_dir / "effective_config.json"

    summary: dict[str, Any] = {
        "kind": "steamer_card_engine.legacy_decision_trace_equivalence.v1",
        "verdict": verdict,
        "data_root": str(data_root),
        "gates": sorted(gates),
        "dataset_count": len(datasets),
        "datasets": datasets,
        "aggregate_by_gate": aggregate_by_gate,
        "summary_path": str(summary_path),
        "mismatch_samples_path": str(mismatch_path),
        "report_path": str(report_path),
    }

    config_path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with mismatch_path.open("w", encoding="utf-8") as file:
        for sample in mismatch_samples:
            file.write(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n")
    report_path.write_text(build_report(summary), encoding="utf-8")

    print(json.dumps({"verdict": verdict, "summary_path": str(summary_path), "report_path": str(report_path)}, ensure_ascii=False))
    return 0 if verdict == "PASS" or args.no_fail_on_mismatch else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare legacy Steamer decisions with card-engine compatibility gates.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gate", action="append", default=None, help="Gate to compare; repeatable; default: REV_SHORT_AFTER_UP")
    parser.add_argument("--decision-file", action="append", help="Specific decisions.jsonl path; repeatable")
    parser.add_argument("--config", help="JSON config override")
    parser.add_argument("--max-mismatch-samples", type=int, default=200)
    parser.add_argument("--no-fail-on-mismatch", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
