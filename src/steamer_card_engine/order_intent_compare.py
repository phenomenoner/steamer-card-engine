from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .legacy_equivalence import LegacyEquivalenceError, resolve_output_dir
from .triangle_compare import _parse_time

ORDER_FIELD_RE = re.compile(r"\b([a-zA-Z_]+):\s*(?:\"([^\"]*)\"|([^,\n]+))")


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def state_hash(state: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(state).encode("utf-8")).hexdigest()[:16]


def _in_gate_slice(row: dict[str, Any], gate: str | None, end_local: str | None) -> bool:
    if gate and row.get("gate") != gate:
        return False
    if end_local is None:
        return True
    now_time = _parse_time((row.get("state") or {}).get("now_time"))
    end_time = _parse_time(end_local)
    return now_time is not None and end_time is not None and now_time <= end_time


def decision_to_intent(row: dict[str, Any], *, source: str, line_no: int) -> dict[str, Any]:
    state = row.get("state") or {}
    symbol = str(row.get("symbol") or state.get("symbol") or "UNKNOWN")
    reason = str(row.get("reason") or "")
    enter = bool(row.get("enter"))
    if enter:
        action = "enter"
        row_kind = "enter_order_intent"
        side = "sell"  # REV_SHORT_AFTER_UP current legacy short entry; future schema should map by strategy id.
        quantity = 1000
        price_basis = "market"
        order_type = "DayTrade"
        tif = "IOC"
    else:
        action = "block"
        if reason.startswith("no_funds") or reason.startswith("no_funds_blocking"):
            row_kind = "risk_block"
        elif reason.startswith("lot_limit_reached"):
            row_kind = "order_block"
        else:
            row_kind = "gate_block"
        side = None
        quantity = None
        price_basis = None
        order_type = None
        tif = None
    return {
        "intent_id": f"{source}:decision:{line_no}",
        "source": source,
        "row_kind": row_kind,
        "symbol": symbol,
        "side": side,
        "action": action,
        "quantity": quantity,
        "price_basis": price_basis,
        "order_type": order_type,
        "order_time_in_force": tif,
        "reason": reason,
        "source_line_no": line_no,
        "state_hash": state_hash(state) if isinstance(state, dict) else None,
        "time": state.get("now_ts") if isinstance(state, dict) else None,
        "local_time": state.get("now_time") if isinstance(state, dict) else None,
    }


def parse_order_result(data: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, quoted, bare in ORDER_FIELD_RE.findall(data or ""):
        value = quoted if quoted != "" else bare.strip()
        out[key] = value.strip()
    return out


def order_event_to_intent(row: dict[str, Any], *, source: str, line_no: int) -> dict[str, Any] | None:
    if row.get("event") != "order_submit":
        return None
    fields = parse_order_result(str(row.get("data") or ""))
    action = str(row.get("action") or "unknown")
    buy_sell = fields.get("buy_sell", "unknown").lower()
    price_type = fields.get("price_type", "unknown")
    quantity = fields.get("quantity")
    try:
        quantity_i = int(str(quantity)) if quantity is not None else None
    except ValueError:
        quantity_i = None
    return {
        "intent_id": f"{source}:order:{line_no}",
        "source": source,
        "row_kind": "actual_order_submit",
        "symbol": str(row.get("symbol") or fields.get("stock_no") or "UNKNOWN"),
        "side": buy_sell,
        "action": action if action in {"enter", "stop", "close", "exit"} else "unknown",
        "quantity": quantity_i,
        "price_basis": price_type.lower(),
        "order_type": fields.get("order_type"),
        "order_time_in_force": fields.get("time_in_force"),
        "reason": str(row.get("user_def") or fields.get("user_def") or ""),
        "source_line_no": line_no,
        "state_hash": None,
        "time": row.get("time"),
        "local_time": fields.get("last_time"),
        "order_no": row.get("order_no") or fields.get("order_no"),
    }


def load_decision_intents(path: Path, *, source: str, gate: str | None, end_local: str | None, enter_only: bool = False) -> list[dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not _in_gate_slice(row, gate, end_local):
                continue
            intent = decision_to_intent(row, source=source, line_no=line_no)
            if enter_only and intent["action"] != "enter":
                continue
            intents.append(intent)
    return intents


def load_order_intents(path: Path, *, source: str) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    intents: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            intent = order_event_to_intent(row, source=source, line_no=line_no)
            if intent is not None:
                intents.append(intent)
    return intents


def intent_signature(intent: dict[str, Any]) -> tuple[Any, ...]:
    return (
        intent.get("symbol"),
        intent.get("action"),
        intent.get("side"),
        intent.get("quantity"),
        intent.get("price_basis"),
        intent.get("order_type"),
        intent.get("order_time_in_force"),
    )


def compare_intent_multisets(left: list[dict[str, Any]], right: list[dict[str, Any]], *, left_name: str, right_name: str) -> dict[str, Any]:
    left_counter = Counter(intent_signature(i) for i in left)
    right_counter = Counter(intent_signature(i) for i in right)
    missing = []
    extra = []
    for sig in sorted(set(left_counter) | set(right_counter), key=str):
        delta = right_counter[sig] - left_counter[sig]
        if delta < 0:
            missing.append({"signature": sig, "count": -delta, "class": classify_signature_gap(sig)})
        elif delta > 0:
            extra.append({"signature": sig, "count": delta, "class": classify_signature_gap(sig)})
    return {
        "left": left_name,
        "right": right_name,
        "left_count": len(left),
        "right_count": len(right),
        "missing_from_right": missing,
        "extra_in_right": extra,
        "match": not missing and not extra,
    }


def classify_signature_gap(sig: tuple[Any, ...]) -> str:
    symbol, action, side, quantity, price_basis, order_type, tif = sig
    if action in {"enter", "stop", "close", "exit"}:
        if quantity is None or price_basis is None or tif is None:
            return "schema_gap"
        return "order_lifecycle_diff"
    if action == "block":
        return "gate_diff"
    return "unknown"


def summarize_intents(name: str, intents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "name": name,
        "count": len(intents),
        "actions": dict(Counter(str(i.get("action")) for i in intents).most_common()),
        "row_kinds": dict(Counter(str(i.get("row_kind")) for i in intents).most_common()),
        "symbols": dict(Counter(str(i.get("symbol")) for i in intents).most_common(20)),
    }


def build_report(summary: dict[str, Any]) -> str:
    lines = ["# Order intent compare report", "", f"## Verdict\n{summary['verdict']}", "", "## Sources"]
    for key, value in summary["sources"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Intent summaries", ""])
    for key, item in summary["intent_summaries"].items():
        lines.extend([f"### {key}", f"- count: {item['count']}", f"- actions: `{item['actions']}`", f"- row_kinds: `{item['row_kinds']}`", f"- symbols_top20: `{item['symbols']}`", ""])
    lines.extend(["## Comparisons", ""])
    for key, comp in summary["comparisons"].items():
        lines.extend([f"### {key}", f"- match: {comp['match']}", f"- left_count: {comp['left_count']}", f"- right_count: {comp['right_count']}", f"- missing_from_right: `{comp['missing_from_right']}`", f"- extra_in_right: `{comp['extra_in_right']}`", ""])
    lines.extend([
        "## Scope / confidence",
        f"- scope: `{summary.get('scope')}`",
        f"- independent_candidate: `{summary.get('independent_candidate')}`",
        f"- live_replacement_confidence: `{summary.get('live_replacement_confidence')}`",
        f"- known_gaps: `{summary.get('known_gaps')}`",
        "",
        "## Notes",
        "- v1 reconstructs entry order intent and actual order_submit intent. Exit/position-state parity is a later slice.",
        "- A clean enter-intent smoke is necessary but not sufficient for live replacement.",
    ])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    output_dir = resolve_output_dir(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    legacy_decisions = Path(args.legacy_decisions).resolve()
    candidate_decisions = Path(args.candidate_decisions).resolve()
    legacy_orders = Path(args.legacy_orders).resolve() if args.legacy_orders else None

    legacy_enter = load_decision_intents(legacy_decisions, source="legacy_decisions", gate=args.gate, end_local=args.end_local, enter_only=True)
    candidate_enter = load_decision_intents(candidate_decisions, source="candidate_decisions", gate=args.gate, end_local=args.end_local, enter_only=True)
    actual_orders = load_order_intents(legacy_orders, source="legacy_orders") if legacy_orders else []
    actual_enter_orders = [i for i in actual_orders if i.get("action") == "enter"]

    comparisons = {
        "legacy_enter_vs_candidate_enter": compare_intent_multisets(legacy_enter, candidate_enter, left_name="legacy_enter", right_name="candidate_enter"),
    }
    if legacy_orders:
        comparisons["legacy_enter_vs_actual_order_submit"] = compare_intent_multisets(legacy_enter, actual_enter_orders, left_name="legacy_enter", right_name="actual_enter_order_submit")

    independent_candidate = legacy_decisions != candidate_decisions
    raw_match = all(c["match"] for c in comparisons.values())
    if raw_match and independent_candidate:
        verdict = "PASS_ENTER_INTENT_SMOKE_INDEPENDENT_CANDIDATE"
    elif raw_match:
        verdict = "PASS_ENTER_INTENT_SMOKE_ONLY"
    else:
        verdict = "NEEDS_INTENT_ALIGNMENT_WORK"
    paths = {
        "legacy_enter_intents": output_dir / "order_intents_legacy.jsonl",
        "candidate_enter_intents": output_dir / "order_intents_candidate.jsonl",
        "actual_order_intents": output_dir / "order_intents_actual_legacy.jsonl",
        "intent_diff": output_dir / "intent_diff.jsonl",
        "scenario_spec": output_dir / "scenario_spec.json",
        "summary": output_dir / "intent_compare_summary.json",
        "report": output_dir / "intent_compare_report.md",
    }
    for key, intents in [("legacy_enter_intents", legacy_enter), ("candidate_enter_intents", candidate_enter), ("actual_order_intents", actual_orders)]:
        with paths[key].open("w", encoding="utf-8") as file:
            for intent in intents:
                file.write(json.dumps(intent, ensure_ascii=False, sort_keys=True) + "\n")
    with paths["intent_diff"].open("w", encoding="utf-8") as file:
        for name, comparison in comparisons.items():
            for item in comparison["missing_from_right"]:
                file.write(json.dumps({"comparison": name, "direction": "missing_from_right", **item}, ensure_ascii=False, sort_keys=True) + "\n")
            for item in comparison["extra_in_right"]:
                file.write(json.dumps({"comparison": name, "direction": "extra_in_right", **item}, ensure_ascii=False, sort_keys=True) + "\n")
    scenario_spec = {
        "kind": "steamer_card_engine.order_intent_scenario.v1",
        "scope": "entry-intent-smoke-only",
        "gate": args.gate,
        "end_local": args.end_local,
        "independent_candidate": independent_candidate,
        "live_replacement_confidence": False,
        "known_gaps": [
            "candidate trace may be same source as legacy unless independent_candidate=true",
            "entry intents only; exits/stops/trailing are out of scope",
            "multiset compare; sequence/timing parity is out of scope",
            "broker/account/position/open-order snapshots are out of scope",
            "REV_SHORT_AFTER_UP short-entry order shape is hardcoded in v1",
        ],
    }
    paths["scenario_spec"].write_text(json.dumps(scenario_spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "kind": "steamer_card_engine.order_intent_compare.v1",
        "verdict": verdict,
        "gate": args.gate,
        "end_local": args.end_local,
        "scope": "entry-intent-smoke-only",
        "live_replacement_confidence": False,
        "independent_candidate": independent_candidate,
        "known_gaps": scenario_spec["known_gaps"],
        "sources": {
            "legacy_decisions": str(legacy_decisions),
            "candidate_decisions": str(candidate_decisions),
            "legacy_orders": str(legacy_orders) if legacy_orders else None,
        },
        "intent_summaries": {
            "legacy_enter": summarize_intents("legacy_enter", legacy_enter),
            "candidate_enter": summarize_intents("candidate_enter", candidate_enter),
            "actual_orders": summarize_intents("actual_orders", actual_orders),
        },
        "comparisons": comparisons,
        "artifacts": {key: str(value) for key, value in paths.items()},
    }
    paths["summary"].write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    paths["report"].write_text(build_report(summary), encoding="utf-8")
    print(json.dumps({"verdict": verdict, "summary_path": str(paths["summary"]), "report_path": str(paths["report"])}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconstruct and compare Steamer order intent traces.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--legacy-decisions", required=True)
    parser.add_argument("--candidate-decisions", required=True)
    parser.add_argument("--legacy-orders")
    parser.add_argument("--gate", default="REV_SHORT_AFTER_UP")
    parser.add_argument("--end-local")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
