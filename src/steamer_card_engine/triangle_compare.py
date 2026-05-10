from __future__ import annotations

import argparse
from collections import Counter
from datetime import time
import json
from pathlib import Path
from typing import Any

from .legacy_equivalence import GATE_EVALUATORS, LegacyEquivalenceError, load_config, normalize_state, resolve_output_dir


def _parse_time(value: Any) -> time | None:
    if isinstance(value, time):
        return value
    if isinstance(value, str) and value:
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None
    return None


def _row_in_slice(row: dict[str, Any], gate: str, end_local: str | None) -> bool:
    if row.get("gate") != gate:
        return False
    if end_local is None:
        return True
    state = row.get("state") or {}
    now_time = _parse_time(state.get("now_time"))
    end_time = _parse_time(end_local)
    if now_time is None or end_time is None:
        return False
    return now_time <= end_time


def load_trace(path: Path, *, gate: str, end_local: str | None = None, max_rows: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if max_rows is not None and len(rows) >= max_rows:
                break
            if not line.strip():
                continue
            row = json.loads(line)
            if _row_in_slice(row, gate, end_local):
                row["_line_no"] = line_no
                rows.append(row)
    return rows


def build_candidate_from_trace(rows: list[dict[str, Any]], *, gate: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    evaluator = GATE_EVALUATORS[gate]
    out: list[dict[str, Any]] = []
    for row in rows:
        state = normalize_state(row.get("state") or {})
        decision = evaluator(state, cfg)
        out.append(
            {
                "symbol": row.get("symbol") or state.get("symbol"),
                "gate": gate,
                "enter": decision.enter,
                "reason": decision.reason,
                "state": row.get("state") or {},
                "_source_line_no": row.get("_line_no"),
            }
        )
    return out


def summarize_trace(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons = Counter(str(row.get("reason")) for row in rows)
    symbols = Counter(str(row.get("symbol") or (row.get("state") or {}).get("symbol") or "UNKNOWN") for row in rows)
    return {
        "name": name,
        "rows": len(rows),
        "enter_true": sum(1 for row in rows if bool(row.get("enter"))),
        "reason_top20": dict(reasons.most_common(20)),
        "symbol_count": len(symbols),
        "symbol_top20": dict(symbols.most_common(20)),
    }


def compare_summaries(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    reason_keys = sorted(set(left["reason_top20"]) | set(right["reason_top20"]))
    reason_delta = {
        key: int(right["reason_top20"].get(key, 0)) - int(left["reason_top20"].get(key, 0))
        for key in reason_keys
        if int(right["reason_top20"].get(key, 0)) != int(left["reason_top20"].get(key, 0))
    }
    return {
        "left": left["name"],
        "right": right["name"],
        "row_delta": right["rows"] - left["rows"],
        "enter_true_delta": right["enter_true"] - left["enter_true"],
        "symbol_count_delta": right["symbol_count"] - left["symbol_count"],
        "reason_delta_top20_scope": reason_delta,
    }


def build_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Triangle trace compare report",
        "",
        f"## Verdict\n{summary['verdict']}",
        "",
        "## Trace summaries",
        "",
    ]
    for name, trace_summary in summary["traces"].items():
        lines.extend(
            [
                f"### {name}",
                f"- rows: {trace_summary['rows']}",
                f"- enter_true: {trace_summary['enter_true']}",
                f"- symbol_count: {trace_summary['symbol_count']}",
                f"- reason_top20: `{trace_summary['reason_top20']}`",
                "",
            ]
        )
    lines.extend(["## Pairwise deltas", ""])
    for key, delta in summary["pairwise"].items():
        lines.extend(
            [
                f"### {key}",
                f"- row_delta: {delta['row_delta']}",
                f"- enter_true_delta: {delta['enter_true_delta']}",
                f"- symbol_count_delta: {delta['symbol_count_delta']}",
                f"- reason_delta_top20_scope: `{delta['reason_delta_top20_scope']}`",
                "",
            ]
        )
    lines.extend([
        "## Interpretation",
        "- A-vs-B isolates historical/runtime lineage and replay-substrate gaps.",
        "- B-vs-C isolates card-engine semantic replication. If C is generated from B state, this should be exact unless card semantics diverge.",
        "- A-vs-C remains useful as an operational parity signal but should not be used alone as truth.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(Path(args.config).resolve() if args.config else None)
    gate = args.gate

    a_rows = load_trace(Path(args.a_decisions).resolve(), gate=gate, end_local=args.end_local, max_rows=args.max_rows)
    b_rows = load_trace(Path(args.b_decisions).resolve(), gate=gate, end_local=args.end_local, max_rows=args.max_rows)
    if args.c_decisions:
        c_rows = load_trace(Path(args.c_decisions).resolve(), gate=gate, end_local=args.end_local, max_rows=args.max_rows)
        c_source = str(Path(args.c_decisions).resolve())
    else:
        c_rows = build_candidate_from_trace(b_rows, gate=gate, cfg=cfg)
        c_source = "generated-from-B-state"

    if not a_rows or not b_rows or not c_rows:
        raise LegacyEquivalenceError("A/B/C traces must all have at least one matching row")

    trace_summaries = {
        "A_historical": summarize_trace("A_historical", a_rows),
        "B_latest_legacy_replay": summarize_trace("B_latest_legacy_replay", b_rows),
        "C_card_candidate": summarize_trace("C_card_candidate", c_rows),
    }
    pairwise = {
        "A_vs_B": compare_summaries(trace_summaries["A_historical"], trace_summaries["B_latest_legacy_replay"]),
        "B_vs_C": compare_summaries(trace_summaries["B_latest_legacy_replay"], trace_summaries["C_card_candidate"]),
        "A_vs_C": compare_summaries(trace_summaries["A_historical"], trace_summaries["C_card_candidate"]),
    }
    b_vs_c_clean = pairwise["B_vs_C"]["row_delta"] == 0 and pairwise["B_vs_C"]["enter_true_delta"] == 0 and not pairwise["B_vs_C"]["reason_delta_top20_scope"]
    verdict = "PASS_BC_SEMANTICS" if b_vs_c_clean else "NEEDS_CARD_SEMANTIC_REVIEW"

    summary_path = output_dir / "triangle_compare_summary.json"
    report_path = output_dir / "triangle_compare_report.md"
    summary = {
        "kind": "steamer_card_engine.triangle_compare.v1",
        "verdict": verdict,
        "gate": gate,
        "end_local": args.end_local,
        "sources": {
            "A_historical": str(Path(args.a_decisions).resolve()),
            "B_latest_legacy_replay": str(Path(args.b_decisions).resolve()),
            "C_card_candidate": c_source,
        },
        "traces": trace_summaries,
        "pairwise": pairwise,
        "summary_path": str(summary_path),
        "report_path": str(report_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "summary_path": str(summary_path), "report_path": str(report_path)}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare A/B/C Steamer decision traces at summary/invariant level.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gate", default="REV_SHORT_AFTER_UP")
    parser.add_argument("--a-decisions", required=True, help="Historical legacy decisions.jsonl")
    parser.add_argument("--b-decisions", required=True, help="Latest legacy replay decisions.jsonl")
    parser.add_argument("--c-decisions", help="Optional card candidate decisions.jsonl; default generates C from B state")
    parser.add_argument("--config")
    parser.add_argument("--end-local")
    parser.add_argument("--max-rows", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
