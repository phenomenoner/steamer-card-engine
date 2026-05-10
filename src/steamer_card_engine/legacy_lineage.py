from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from .legacy_equivalence import (
    DEFAULT_DATA_ROOT,
    GATE_EVALUATORS,
    SUPPORTED_GATES,
    LegacyEquivalenceError,
    load_config,
    normalize_state,
    resolve_output_dir,
)


RISK_ORDER_PREFIXES = (
    "no_funds",
    "no_funds_blocking",
    "lot_limit_reached",
    "Enter Pause",
)


def classify_mismatch(row: dict[str, Any], candidate_reason: str, candidate_enter: bool) -> tuple[str, str]:
    legacy_reason = str(row.get("reason"))
    legacy_enter = bool(row.get("enter"))
    state = row.get("state") or {}

    if legacy_reason.startswith(RISK_ORDER_PREFIXES):
        return "risk_order_layer", f"historical runtime/order layer reason: {legacy_reason.split(':', 1)[0]}"

    if legacy_reason.startswith("now_time_") or candidate_reason.startswith("now_time_"):
        if legacy_reason != candidate_reason:
            return "policy_lineage", f"market gate/time policy differs: {legacy_reason} vs {candidate_reason}"

    if "trend_conflict" in legacy_reason or "trend_conflict" in candidate_reason:
        if legacy_reason != candidate_reason:
            return "policy_lineage", "trend-conflict rule presence/threshold differs"

    if legacy_enter != candidate_enter:
        if legacy_reason.startswith("enter_") or candidate_reason.startswith("enter_"):
            return "gate_semantics", f"enter decision differs: {legacy_enter} vs {candidate_enter}"
        return "gate_semantics", "boolean enter differs"

    if legacy_reason != candidate_reason:
        if legacy_reason in {"no_recent_high", "angle", "zz_not_down", "not_strong_up", "too_shallow", "above_ema"} and candidate_reason in {
            "no_recent_high",
            "angle",
            "zz_not_down",
            "not_strong_up",
            "too_shallow",
            "above_ema",
        }:
            return "policy_lineage", f"gate order/threshold lineage differs: {legacy_reason} vs {candidate_reason}"
        if not state:
            return "data_quality", "missing state payload"
        return "unknown", f"unclassified reason mismatch: {legacy_reason} vs {candidate_reason}"

    return "match", "no mismatch"


def classify_decision_file(
    path: Path,
    *,
    data_root: Path,
    gates: set[str],
    cfg: dict[str, Any],
    max_samples_per_class: int,
) -> dict[str, Any]:
    try:
        rel = path.relative_to(data_root)
        machine = rel.parts[0]
        date = rel.parts[1]
    except ValueError:
        machine = "external"
        date = path.parent.name

    class_counts: Counter[str] = Counter()
    reason_pair_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows = 0
    mismatches = 0

    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            gate = row.get("gate")
            if gate not in gates:
                continue
            rows += 1
            candidate = GATE_EVALUATORS[gate](normalize_state(row.get("state") or {}), cfg)
            legacy_enter = bool(row.get("enter"))
            legacy_reason = str(row.get("reason"))
            if legacy_enter == candidate.enter and legacy_reason == candidate.reason:
                continue
            mismatches += 1
            klass, detail = classify_mismatch(row, candidate.reason, candidate.enter)
            class_counts[klass] += 1
            reason_pair_counts[f"{legacy_reason} -> {candidate.reason}"] += 1
            if len(samples[klass]) < max_samples_per_class:
                samples[klass].append(
                    {
                        "machine": machine,
                        "date": date,
                        "line_no": line_no,
                        "symbol": row.get("symbol"),
                        "gate": gate,
                        "class": klass,
                        "detail": detail,
                        "legacy_enter": legacy_enter,
                        "candidate_enter": candidate.enter,
                        "legacy_reason": legacy_reason,
                        "candidate_reason": candidate.reason,
                        "state_now_time": (row.get("state") or {}).get("now_time"),
                        "state_now_ts": (row.get("state") or {}).get("now_ts"),
                    }
                )

    return {
        "machine": machine,
        "date": date,
        "source": str(path),
        "rows": rows,
        "mismatches": mismatches,
        "class_counts": dict(class_counts),
        "reason_pair_top20": dict(reason_pair_counts.most_common(20)),
        "samples": dict(samples),
    }


def build_lineage_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Legacy equivalence mismatch lineage report",
        "",
        f"Machine summary: `{summary['summary_path']}`",
        "",
        "## Verdict",
        summary["verdict"],
        "",
        "## Aggregate classes",
        "",
        "| class | count | share of mismatches |",
        "|---|---:|---:|",
    ]
    total = summary["total_mismatches"] or 1
    for klass, count in sorted(summary["aggregate_class_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {klass} | {count} | {count / total:.2%} |")

    lines.extend(["", "## Dataset summaries", ""])
    for dataset in summary["datasets"]:
        lines.append(
            f"- `{dataset['machine']}/{dataset['date']}` rows={dataset['rows']} mismatches={dataset['mismatches']} classes={dataset['class_counts']}"
        )

    lines.extend(["", "## Top reason pairs", ""])
    for pair, count in summary["aggregate_reason_pair_top30"].items():
        lines.append(f"- `{pair}`: {count}")

    lines.extend([
        "",
        "## Interpretation",
        "- `risk_order_layer` rows should not be forced into card gate logic; model them as runtime/risk-layer decisions.",
        "- `policy_lineage` rows need scenario/config grouping before demanding full-sweep PASS.",
        "- `gate_semantics` rows are the priority bug bucket for card-engine replication once A-vs-B drift is ruled out.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root).resolve()
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    gates = {gate.strip() for gate in (args.gate or ["REV_SHORT_AFTER_UP"]) if gate.strip()}
    unknown = gates - SUPPORTED_GATES
    if unknown:
        raise LegacyEquivalenceError(f"unsupported gates: {sorted(unknown)}")
    cfg = load_config(Path(args.config).resolve() if args.config else None)

    decision_files = [Path(item).resolve() for item in args.decision_file]
    if not decision_files:
        raise LegacyEquivalenceError("at least one --decision-file is required for lineage classification")

    datasets = [
        classify_decision_file(
            path,
            data_root=data_root,
            gates=gates,
            cfg=cfg,
            max_samples_per_class=args.max_samples_per_class,
        )
        for path in decision_files
    ]
    datasets = [dataset for dataset in datasets if dataset["rows"]]
    if not datasets:
        raise LegacyEquivalenceError("no matching decision rows found")

    class_counts: Counter[str] = Counter()
    reason_pair_counts: Counter[str] = Counter()
    all_samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for dataset in datasets:
        class_counts.update(dataset["class_counts"])
        reason_pair_counts.update(dataset["reason_pair_top20"])
        for klass, rows in dataset["samples"].items():
            remaining = max(0, args.max_samples_per_class - len(all_samples[klass]))
            if remaining:
                all_samples[klass].extend(rows[:remaining])

    total_rows = sum(dataset["rows"] for dataset in datasets)
    total_mismatches = sum(dataset["mismatches"] for dataset in datasets)
    classified = total_mismatches - class_counts.get("unknown", 0)
    classified_rate = classified / total_mismatches if total_mismatches else 1.0
    verdict = "PASS_CLASSIFIED" if classified_rate >= args.min_classified_rate else "NEEDS_MORE_EVIDENCE"

    summary_path = output_dir / "lineage_classification.json"
    report_path = output_dir / "lineage_report.md"
    samples_path = output_dir / "lineage_samples.json"
    summary = {
        "kind": "steamer_card_engine.legacy_equivalence_lineage.v1",
        "verdict": verdict,
        "data_root": str(data_root),
        "gates": sorted(gates),
        "dataset_count": len(datasets),
        "total_rows": total_rows,
        "total_mismatches": total_mismatches,
        "classified_rate": classified_rate,
        "aggregate_class_counts": dict(class_counts),
        "aggregate_reason_pair_top30": dict(reason_pair_counts.most_common(30)),
        "datasets": datasets,
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "samples_path": str(samples_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    samples_path.write_text(json.dumps(all_samples, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(build_lineage_report(summary), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "classified_rate": classified_rate, "summary_path": str(summary_path), "report_path": str(report_path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Classify legacy/card decision mismatches by likely root cause.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gate", action="append", default=None)
    parser.add_argument("--decision-file", action="append", required=True)
    parser.add_argument("--config")
    parser.add_argument("--max-samples-per-class", type=int, default=20)
    parser.add_argument("--min-classified-rate", type=float, default=0.90)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
