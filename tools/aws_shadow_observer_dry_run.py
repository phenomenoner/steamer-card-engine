#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def legacy_order_intent_rows(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Keep this dry-run hook deliberately schema-light; production compare uses
    # steamer_card_engine.order_intent_compare. The hook's job is artifact shape.
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(orders, start=1):
        if row.get("event") != "order_submit" or row.get("action") != "enter":
            continue
        out.append(
            {
                "source": "legacy_order_event",
                "source_line_no": idx,
                "symbol": str(row.get("symbol") or "UNKNOWN"),
                "action": row.get("action") or "unknown",
                "user_def": row.get("user_def"),
                "time": row.get("time"),
                "raw_event": row,
            }
        )
    return out


def card_shadow_intent_rows(candidate_decisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(candidate_decisions, start=1):
        state = row.get("state") or {}
        if row.get("enter"):
            out.append(
                {
                    "source": "card_shadow_decision",
                    "source_line_no": idx,
                    "symbol": str(row.get("symbol") or state.get("symbol") or "UNKNOWN"),
                    "action": "enter",
                    "side": "sell",
                    "quantity": 1000,
                    "price_basis": "market",
                    "order_type": "DayTrade",
                    "order_time_in_force": "IOC",
                    "reason": row.get("reason"),
                    "local_time": state.get("now_time"),
                    "time": state.get("now_ts"),
                }
            )
    return out


def active_universe_from_sources(*sources: list[dict[str, Any]]) -> list[str]:
    symbols: set[str] = set()
    for rows in sources:
        for row in rows:
            symbol = row.get("symbol") or (row.get("state") or {}).get("symbol")
            if symbol:
                symbols.add(str(symbol))
    return sorted(symbols)


def build_summary(*, day: str, run_goal: str, output_dir: Path, legacy_intents: list[dict[str, Any]], card_intents: list[dict[str, Any]], active_universe: list[str]) -> dict[str, Any]:
    legacy_counts = Counter((row.get("symbol"), row.get("action")) for row in legacy_intents)
    card_counts = Counter((row.get("symbol"), row.get("action")) for row in card_intents)
    diff_rows = []
    for key in sorted(set(legacy_counts) | set(card_counts), key=str):
        delta = card_counts[key] - legacy_counts[key]
        if delta:
            diff_rows.append({"symbol": key[0], "action": key[1], "legacy_count": legacy_counts[key], "card_count": card_counts[key], "delta": delta})
    verdict = "PASS_SHADOW_OBSERVER_DRY_RUN_ARTIFACTS" if output_dir.exists() else "FAIL_SHADOW_OBSERVER_DRY_RUN"
    if diff_rows:
        verdict = "SHADOW_OBSERVER_DRY_RUN_HAS_INTENT_DIFFS"
    return {
        "kind": "steamer_card_engine.aws_shadow_observer_dry_run.v1",
        "day": day,
        "run_goal": run_goal,
        "verdict": verdict,
        "live_replacement_confidence": False,
        "observer_only": True,
        "submits_orders": False,
        "owns_ec2_lifecycle": False,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "active_universe_count": len(active_universe),
        "legacy_intent_count": len(legacy_intents),
        "card_shadow_intent_count": len(card_intents),
        "intent_diff_count": len(diff_rows),
        "artifacts": {
            "scenario_spec": str(output_dir / "scenario_spec.json"),
            "active_universe": str(output_dir / "active_universe.json"),
            "broker_state_snapshots": str(output_dir / "broker_state_snapshots.jsonl"),
            "legacy_order_intents": str(output_dir / "legacy_order_intents.jsonl"),
            "card_shadow_order_intents": str(output_dir / "card_shadow_order_intents.jsonl"),
            "intent_diff": str(output_dir / "intent_diff.jsonl"),
            "intent_compare_summary": str(output_dir / "intent_compare_summary.json"),
            "summary_md": str(output_dir / "summary.md"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create AWS shadow comparison observer artifacts in dry-run/offline mode.")
    parser.add_argument("--day", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--legacy-orders")
    parser.add_argument("--legacy-decisions")
    parser.add_argument("--candidate-decisions")
    parser.add_argument("--run-goal", default="REV_SHORT_AFTER_UP entry order intent only")
    args = parser.parse_args()

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    legacy_orders = read_jsonl(Path(args.legacy_orders).resolve()) if args.legacy_orders else []
    legacy_decisions = read_jsonl(Path(args.legacy_decisions).resolve()) if args.legacy_decisions else []
    candidate_decisions = read_jsonl(Path(args.candidate_decisions).resolve()) if args.candidate_decisions else []

    legacy_intents = legacy_order_intent_rows(legacy_orders)
    card_intents = card_shadow_intent_rows(candidate_decisions)
    active_universe = active_universe_from_sources(legacy_orders, legacy_decisions, candidate_decisions)

    scenario = {
        "kind": "steamer_card_engine.aws_shadow_scenario.v1",
        "day": args.day,
        "run_goal": args.run_goal,
        "observer_only": True,
        "submits_orders": False,
        "owns_ec2_lifecycle": False,
        "inputs": {
            "legacy_orders": args.legacy_orders,
            "legacy_decisions": args.legacy_decisions,
            "candidate_decisions": args.candidate_decisions,
        },
    }
    (output_dir / "scenario_spec.json").write_text(json.dumps(scenario, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "active_universe.json").write_text(json.dumps({"symbols": active_universe}, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(output_dir / "broker_state_snapshots.jsonl", [{"kind": "placeholder", "reason": "dry_run_no_broker_snapshot", "live_replacement_confidence": False}])
    write_jsonl(output_dir / "legacy_order_intents.jsonl", legacy_intents)
    write_jsonl(output_dir / "card_shadow_order_intents.jsonl", card_intents)

    legacy_counts = Counter((row.get("symbol"), row.get("action")) for row in legacy_intents)
    card_counts = Counter((row.get("symbol"), row.get("action")) for row in card_intents)
    diff_rows = []
    for key in sorted(set(legacy_counts) | set(card_counts), key=str):
        delta = card_counts[key] - legacy_counts[key]
        if delta:
            diff_rows.append({"class": "order_lifecycle_diff", "symbol": key[0], "action": key[1], "legacy_count": legacy_counts[key], "card_count": card_counts[key], "delta": delta})
    write_jsonl(output_dir / "intent_diff.jsonl", diff_rows)

    summary = build_summary(day=args.day, run_goal=args.run_goal, output_dir=output_dir, legacy_intents=legacy_intents, card_intents=card_intents, active_universe=active_universe)
    (output_dir / "intent_compare_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "summary.md").write_text(
        "# AWS shadow observer dry-run\n\n"
        f"## Verdict\n{summary['verdict']}\n\n"
        f"- day: {args.day}\n"
        f"- observer_only: true\n"
        f"- submits_orders: false\n"
        f"- owns_ec2_lifecycle: false\n"
        f"- active_universe_count: {len(active_universe)}\n"
        f"- legacy_intent_count: {len(legacy_intents)}\n"
        f"- card_shadow_intent_count: {len(card_intents)}\n"
        f"- intent_diff_count: {summary['intent_diff_count']}\n",
        encoding="utf-8",
    )
    print(json.dumps({"verdict": summary["verdict"], "output_dir": str(output_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
