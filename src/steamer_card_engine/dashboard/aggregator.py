from __future__ import annotations

from collections import Counter
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from .fixtures import FixtureDay, discover_fixture_days, repo_root


class DashboardDataError(Exception):
    """Raised when a requested dashboard fixture cannot be resolved."""


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as file:
        return sum(1 for line in file if line.strip())


def _sample_jsonl(path: Path, sample_size: int = 12) -> list[dict[str, Any]]:
    total = _count_jsonl(path)
    if total == 0:
        return []
    if total <= sample_size:
        return _load_jsonl(path)

    target_indexes = {round(index * (total - 1) / (sample_size - 1)) for index in range(sample_size)}
    sampled: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            if index not in target_indexes:
                continue
            line = line.strip()
            if not line:
                continue
            sampled.append(json.loads(line))
    return sampled


def _safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _top_counter(counter: Counter[str], limit: int = 8) -> list[dict[str, Any]]:
    return [{"label": label, "count": count} for label, count in counter.most_common(limit)]


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sample_rows(rows: list[dict[str, Any]], sample_size: int = 12) -> list[dict[str, Any]]:
    if not rows:
        return []
    if len(rows) <= sample_size:
        return rows

    target_indexes = {round(index * (len(rows) - 1) / (sample_size - 1)) for index in range(sample_size)}
    return [row for index, row in enumerate(rows) if index in target_indexes]


def _extract_markdown_notes(markdown: str) -> list[str]:
    lines = markdown.splitlines()
    try:
        start = lines.index("## Notes") + 1
    except ValueError:
        return []

    notes: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            notes.append(stripped.lstrip("-").strip())
    return notes[:8]


def _delta_counts(counts: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for key, lane_counts in counts.items():
        baseline = int(lane_counts.get("baseline", 0))
        candidate = int(lane_counts.get("candidate", 0))
        out[key] = {"baseline": baseline, "candidate": candidate, "delta": candidate - baseline}
    return out


def _universe_surface(scenario_spec: dict[str, Any]) -> dict[str, Any]:
    market = scenario_spec.get("market_clock", {})
    session = scenario_spec.get("session_slice", {})
    symbol_set = scenario_spec.get("symbol_set", {})
    symbols = list(symbol_set.get("symbols", []) or [])

    return {
        "scenario_id": scenario_spec.get("scenario_id"),
        "calendar": market.get("calendar"),
        "timezone": market.get("timezone"),
        "session": {
            "session_date": session.get("session_date"),
            "slice_label": session.get("slice_label"),
            "start_local": session.get("start_local"),
            "end_local": session.get("end_local"),
        },
        "event_source": {
            "source_kind": scenario_spec.get("event_source", {}).get("source_kind"),
            "source_id": scenario_spec.get("event_source", {}).get("source_id"),
            "time_range_utc": scenario_spec.get("event_source", {}).get("time_range_utc"),
        },
        "determinism": scenario_spec.get("determinism", {}),
        "symbol_set": {
            "symbol_set_id": symbol_set.get("symbol_set_id"),
            "mode": symbol_set.get("mode"),
        },
        "symbol_count": len(symbols),
        "symbol_samples": symbols[:16],
    }


def _lane_payload(
    lane: str,
    bundle_dir: Path,
    repo: Path,
) -> dict[str, Any]:
    run_manifest = _load_json(bundle_dir / "run-manifest.json")
    scenario_spec = _load_json(bundle_dir / "scenario-spec.json")
    config_snapshot = _load_json(bundle_dir / "config-snapshot.json")
    deck = {
        "deck_id": config_snapshot.get("deck_id"),
        "deck_version": config_snapshot.get("deck_version"),
        "config_hash": config_snapshot.get("config_hash"),
        "cards": config_snapshot.get("cards", []),
        "card_count": len(config_snapshot.get("cards", [])),
    }
    anomalies = _load_json(bundle_dir / "anomalies.json").get("anomalies", [])
    pnl_summary = _load_json(bundle_dir / "pnl-summary.json")
    intents = _load_jsonl(bundle_dir / "intent-log.jsonl")
    risks = _load_jsonl(bundle_dir / "risk-receipts.jsonl")
    executions = _load_jsonl(bundle_dir / "execution-log.jsonl")
    features = _load_jsonl(bundle_dir / "feature-provenance.jsonl")

    counts = {
        "events": _count_jsonl(bundle_dir / "event-log.jsonl"),
        "intents": len(intents),
        "risk_decisions": len(risks),
        "execution_requests": len(executions),
        "fills": _count_jsonl(bundle_dir / "fills.jsonl"),
        "orders": _count_jsonl(bundle_dir / "order-lifecycle.jsonl"),
        "positions": _count_jsonl(bundle_dir / "positions.jsonl"),
    }

    intent_by_id = {row["intent_id"]: row for row in intents}
    risk_by_id = {row["risk_decision_id"]: row for row in risks}

    card_rollups: dict[tuple[str, str], dict[str, Any]] = {}
    risk_reason_counts: dict[tuple[str, str], Counter[str]] = {}

    for intent in intents:
        key = (intent["card_id"], intent.get("card_version", "unknown"))
        summary = card_rollups.setdefault(
            key,
            {
                "card_id": intent["card_id"],
                "card_version": intent.get("card_version", "unknown"),
                "deck_id": intent.get("deck_id"),
                "lane": lane,
                "intents_total": 0,
                "signal_intents": 0,
                "entry_intents": 0,
                "symbols": Counter(),
                "sides": Counter(),
                "intent_reasons": Counter(),
                "allowed_risk": 0,
                "blocked_risk": 0,
                "execution_requests": 0,
                "feature_records": 0,
            },
        )
        summary["intents_total"] += 1
        summary["symbols"][intent["symbol"]] += 1
        summary["sides"][intent["side"]] += 1
        summary["intent_reasons"][intent["reason_code"]] += 1
        if str(intent.get("event_id", "")).startswith("decision-signal-"):
            summary["signal_intents"] += 1
        if str(intent.get("event_id", "")).startswith("decision-entry-"):
            summary["entry_intents"] += 1

    for risk in risks:
        intent = intent_by_id.get(risk["intent_id"])
        if intent is None:
            continue
        key = (intent["card_id"], intent.get("card_version", "unknown"))
        summary = card_rollups[key]
        if risk["decision"] == "allow":
            summary["allowed_risk"] += 1
        else:
            summary["blocked_risk"] += 1
        risk_reason_counts.setdefault(key, Counter())[risk["reason_code"]] += 1

    for execution in executions:
        risk = risk_by_id.get(execution["risk_decision_id"])
        intent = intent_by_id.get(risk["intent_id"]) if risk else None
        if intent is None:
            continue
        key = (intent["card_id"], intent.get("card_version", "unknown"))
        card_rollups[key]["execution_requests"] += 1

    for feature in features:
        for key, summary in card_rollups.items():
            if feature["symbol"] in summary["symbols"]:
                summary["feature_records"] += 1
                break

    cards = []
    for key, summary in card_rollups.items():
        cards.append(
            {
                "id": f"{lane}:{summary['card_id']}",
                "card_id": summary["card_id"],
                "card_version": summary["card_version"],
                "deck_id": summary["deck_id"],
                "lane": lane,
                "intent_count": summary["intents_total"],
                "signal_intent_count": summary["signal_intents"],
                "entry_intent_count": summary["entry_intents"],
                "allowed_risk_count": summary["allowed_risk"],
                "blocked_risk_count": summary["blocked_risk"],
                "execution_request_count": summary["execution_requests"],
                "feature_record_count": summary["feature_records"],
                "top_symbols": _top_counter(summary["symbols"], limit=6),
                "sides": _top_counter(summary["sides"], limit=4),
                "reason_distribution": _top_counter(summary["intent_reasons"], limit=8),
                "risk_reason_distribution": _top_counter(risk_reason_counts.get(key, Counter()), limit=8),
                "anomaly_refs": [anomaly["anomaly_id"] for anomaly in anomalies],
            }
        )

    cards.sort(
        key=lambda card: (
            -card["execution_request_count"],
            -card["allowed_risk_count"],
            -card["intent_count"],
            card["card_id"],
        )
    )

    market_samples = _sample_jsonl(bundle_dir / "event-log.jsonl", sample_size=12)

    timeline: list[dict[str, Any]] = [
        {
            "event_key": f"{lane}:started",
            "timestamp": run_manifest["started_at_utc"],
            "lane": lane,
            "kind": "run-start",
            "title": f"{lane} session started",
            "subtitle": run_manifest["scenario_id"],
            "symbol": None,
            "status": "info",
            "details": {"run_id": run_manifest["run_id"]},
        },
        {
            "event_key": f"{lane}:ended",
            "timestamp": run_manifest["ended_at_utc"],
            "lane": lane,
            "kind": "run-end",
            "title": f"{lane} session ended",
            "subtitle": run_manifest["status"],
            "symbol": None,
            "status": "info",
            "details": {"run_id": run_manifest["run_id"]},
        },
    ]

    for anomaly in anomalies:
        timeline.append(
            {
                "event_key": f"{lane}:{anomaly['anomaly_id']}",
                "timestamp": anomaly["detected_at_utc"],
                "lane": lane,
                "kind": "anomaly",
                "title": anomaly["category"],
                "subtitle": anomaly["message"],
                "symbol": None,
                "status": anomaly["severity"],
                "details": anomaly,
            }
        )

    for risk in risks:
        if risk["decision"] != "allow":
            continue
        intent = intent_by_id.get(risk["intent_id"])
        timeline.append(
            {
                "event_key": f"{lane}:{risk['risk_decision_id']}",
                "timestamp": risk["decision_time_utc"],
                "lane": lane,
                "kind": "risk-allow",
                "title": f"Risk allow {risk['reason_code']}",
                "subtitle": risk["policy_name"],
                "symbol": intent["symbol"] if intent else None,
                "status": "positive",
                "details": risk,
            }
        )

    blocked_added = 0
    for risk in risks:
        if risk["decision"] != "block" or blocked_added >= 16:
            continue
        intent = intent_by_id.get(risk["intent_id"])
        timeline.append(
            {
                "event_key": f"{lane}:{risk['risk_decision_id']}:block",
                "timestamp": risk["decision_time_utc"],
                "lane": lane,
                "kind": "risk-block",
                "title": f"Risk block {risk['reason_code']}",
                "subtitle": risk["policy_name"],
                "symbol": intent["symbol"] if intent else None,
                "status": "warn",
                "details": risk,
            }
        )
        blocked_added += 1

    for execution in executions:
        timeline.append(
            {
                "event_key": f"{lane}:{execution['exec_request_id']}",
                "timestamp": execution["request_time_utc"],
                "lane": lane,
                "kind": "execution-request",
                "title": f"{execution['side']} {execution['symbol']} execution request",
                "subtitle": execution["order_type"],
                "symbol": execution["symbol"],
                "status": "neutral",
                "details": execution,
            }
        )

    for sample in market_samples:
        payload = sample.get("payload", {})
        timeline.append(
            {
                "event_key": f"{lane}:{sample['event_id']}",
                "timestamp": sample["event_time_utc"],
                "lane": lane,
                "kind": "market-sample",
                "title": f"Market sample {sample['symbol']}",
                "subtitle": f"price={payload.get('price')} size={payload.get('size')}",
                "symbol": sample["symbol"],
                "status": "info",
                "details": sample,
            }
        )

    transaction_surface = {
        "lane": lane,
        "counts": counts,
        "pnl_summary": pnl_summary,
        "records": {
            "fills": _load_jsonl(bundle_dir / "fills.jsonl"),
            "orders": _load_jsonl(bundle_dir / "order-lifecycle.jsonl"),
            "positions": _load_jsonl(bundle_dir / "positions.jsonl"),
        },
        "empty_state": {
            "is_empty": counts["fills"] == 0 and counts["orders"] == 0 and counts["positions"] == 0,
            "empty_reason": (
                "No populated fill, order-lifecycle, or position rows exist in this committed fixture bundle."
            ),
            "truth_note": (
                "Intent, risk, and execution shells are present, but trade-surface artifacts remain empty "
                "placeholders in the March demo set."
            ),
        },
    }

    return {
        "lane": lane,
        "bundle_dir": str(bundle_dir),
        "bundle_relpath": _safe_relpath(bundle_dir, repo),
        "run_manifest": run_manifest,
        "scenario_spec": scenario_spec,
        "config_snapshot": config_snapshot,
        "deck": deck,
        "anomalies": anomalies,
        "pnl_summary": pnl_summary,
        "counts": counts,
        "cards": cards,
        "timeline": timeline,
        "transaction_surface": transaction_surface,
        "feature_samples": features[:12],
    }


def _resolve_fixture(date: str, root: Path | None = None) -> FixtureDay:
    for fixture in discover_fixture_days(root):
        if fixture.date == date:
            return fixture
    raise DashboardDataError(f"unknown fixture date: {date}")


def list_fixture_dates(root: Path | None = None) -> list[dict[str, Any]]:
    repo = root or repo_root()
    items = []
    for fixture in discover_fixture_days(repo):
        bundle = build_day_bundle(fixture.date, repo)
        items.append(
            {
                "date": fixture.date,
                "hero": fixture.date == max(day.date for day in discover_fixture_days(repo)),
                "compare_status": bundle["compare"]["status"],
                "scenario_id": bundle["daily_summary"]["scenario_id"],
                "comparison_dir": bundle["fixture"]["comparison_dir"],
                "dominant_lane": bundle["daily_summary"]["dominant_lane"],
                "dominant_card": bundle["daily_summary"]["dominant_card"],
                "anomaly_count": bundle["daily_summary"]["anomaly_total"],
                "transaction_state": bundle["transaction_surface"]["empty_state_metadata"]["state"],
                "symbol_count": bundle.get("deck_view", {}).get("universe", {}).get("symbol_count"),
                "calendar": bundle.get("deck_view", {}).get("universe", {}).get("calendar"),
                "timezone": bundle.get("deck_view", {}).get("universe", {}).get("timezone"),
                "candidate_deck_id": next((lane["deck_id"] for lane in bundle["daily_summary"]["lanes"] if lane["lane"] == "steamer-card-engine"), None),
                "baseline_deck_id": next((lane["deck_id"] for lane in bundle["daily_summary"]["lanes"] if lane["lane"] == "baseline-bot"), None),
            }
        )
    return items


@lru_cache(maxsize=16)
def build_day_bundle(date: str, root: Path | None = None) -> dict[str, Any]:
    repo = root or repo_root()
    fixture = _resolve_fixture(date, repo)
    compare_manifest = _load_json(fixture.compare_manifest)
    diff = _load_json(fixture.diff)

    baseline = _lane_payload("baseline-bot", fixture.baseline_dir, repo)
    candidate = _lane_payload("steamer-card-engine", fixture.candidate_dir, repo)
    lanes = [baseline, candidate]
    dominant_lane = max(
        lanes,
        key=lambda lane: (
            lane["counts"]["execution_requests"],
            lane["counts"]["risk_decisions"],
            lane["counts"]["intents"],
            lane["lane"] == "steamer-card-engine",
        ),
    )["lane"]
    all_cards = sorted(
        baseline["cards"] + candidate["cards"],
        key=lambda card: (
            -(card["lane"] == dominant_lane),
            -card["execution_request_count"],
            -card["allowed_risk_count"],
            -card["intent_count"],
            card["lane"],
            card["card_id"],
        ),
    )
    dominant_card = all_cards[0] if all_cards else None

    event_timeline = sorted(
        baseline["timeline"] + candidate["timeline"],
        key=lambda event: (event["timestamp"], event["event_key"]),
    )

    transaction_empty = (
        baseline["transaction_surface"]["empty_state"]["is_empty"]
        and candidate["transaction_surface"]["empty_state"]["is_empty"]
    )

    transaction_surface = {
        "counts": diff["counts"],
        "pnl_reported": diff["pnl_reported"],
        "lanes": {
            baseline["lane"]: baseline["transaction_surface"],
            candidate["lane"]: candidate["transaction_surface"],
        },
        "empty_state_metadata": {
            "state": "empty" if transaction_empty else "partial",
            "empty_reason": (
                "The March demo fixtures carry intent, risk, and execution shells, but no populated fills, "
                "orders, or positions."
            ),
            "truth_note": (
                "Transaction/PnL panels are intentionally read-only and explicit about placeholder-empty trade "
                "surfaces. This is a data contract truth, not a UI loading failure."
            ),
        },
    }

    anomaly_rows = []
    for lane in lanes:
        for anomaly in lane["anomalies"]:
            anomaly_rows.append({**anomaly, "lane": lane["lane"]})
    anomaly_rows.sort(key=lambda item: (item["detected_at_utc"], item["lane"], item["anomaly_id"]))

    daily_summary = {
        "date": date,
        "hero_day": date == discover_fixture_days(repo)[0].date,
        "scenario_id": compare_manifest["scenario"]["scenario_id"],
        "scenario_fingerprint": compare_manifest["scenario"]["scenario_fingerprint"],
        "compare_status": compare_manifest["status"],
        "compare_version": compare_manifest["compare_version"],
        "dominant_lane": dominant_lane,
        "dominant_card": dominant_card["id"] if dominant_card else None,
        "dominant_card_label": (
            f"{dominant_card['lane']} / {dominant_card['card_id']}" if dominant_card else None
        ),
        "anomaly_total": len(anomaly_rows),
        "event_total": baseline["counts"]["events"] + candidate["counts"]["events"],
        "execution_request_total": (
            baseline["counts"]["execution_requests"] + candidate["counts"]["execution_requests"]
        ),
        "intent_total": baseline["counts"]["intents"] + candidate["counts"]["intents"],
        "transaction_state": transaction_surface["empty_state_metadata"]["state"],
        "lanes": [
            {
                "lane": lane["lane"],
                "run_id": lane["run_manifest"]["run_id"],
                "status": lane["run_manifest"]["status"],
                "started_at_utc": lane["run_manifest"]["started_at_utc"],
                "ended_at_utc": lane["run_manifest"]["ended_at_utc"],
                "counts": lane["counts"],
                "entry_count": lane["pnl_summary"]["entry_count"],
                "realized_pnl_net": lane["pnl_summary"]["realized_pnl_net"],
                "anomaly_count": len(lane["anomalies"]),
                "bundle_relpath": lane["bundle_relpath"],
                "deck_id": lane["deck"]["deck_id"],
                "deck_version": lane["deck"]["deck_version"],
                "config_hash": lane["deck"]["config_hash"],
                "card_count": lane["deck"]["card_count"],
                "cards": lane["deck"]["cards"],
            }
            for lane in lanes
        ],
    }

    compare = {
        "status": compare_manifest["status"],
        "compare_version": compare_manifest["compare_version"],
        "comparison_dir": str(fixture.comparison_dir),
        "comparison_relpath": _safe_relpath(fixture.comparison_dir, repo),
        "hard_fail_reasons": compare_manifest["hard_fail_reasons"],
        "execution_model": compare_manifest["execution_model"],
        "scenario": compare_manifest["scenario"],
        "counts": diff["counts"],
        "anomalies": diff["anomalies"],
        "pnl_reported": diff["pnl_reported"],
        "scaffold_placeholders": diff["scaffold_placeholders"],
    }

    snapshots = {
        "scenario": baseline["scenario_spec"],
        "compare-manifest": compare_manifest,
        "compare-diff": diff,
        "baseline-config": baseline["config_snapshot"],
        "candidate-config": candidate["config_snapshot"],
        "baseline-run": baseline["run_manifest"],
        "candidate-run": candidate["run_manifest"],
    }

    compare_summary_markdown = _load_text(fixture.summary)
    compare_notes = _extract_markdown_notes(compare_summary_markdown)
    universe = _universe_surface(candidate["scenario_spec"])
    delta_counts = _delta_counts(diff["counts"])

    deck_cover = {
        "date": date,
        "scenario_id": daily_summary["scenario_id"],
        "compare_status": compare_manifest["status"],
        "dominant_lane": dominant_lane,
        "dominant_card": daily_summary["dominant_card"],
        "dominant_card_label": daily_summary["dominant_card_label"],
        "anomaly_total": daily_summary["anomaly_total"],
        "transaction_state": daily_summary["transaction_state"],
        "delta_counts": delta_counts,
        "scaffold_placeholders": list(diff.get("scaffold_placeholders", {}).keys()),
        "compare_notes": compare_notes,
    }

    deck_view = {
        "date": date,
        "fixture": {
            "comparison_relpath": _safe_relpath(fixture.comparison_dir, repo),
            "baseline_bundle_relpath": _safe_relpath(fixture.baseline_dir, repo),
            "candidate_bundle_relpath": _safe_relpath(fixture.candidate_dir, repo),
        },
        "cover": deck_cover,
        "universe": universe,
        "strategy": {
            "dominant_lane": dominant_lane,
            "dominant_card": daily_summary["dominant_card"],
            "lanes": {
                baseline["lane"]: baseline["deck"],
                candidate["lane"]: candidate["deck"],
            },
            "cards": all_cards,
        },
        "compare": compare,
        "evidence": {
            "anomalies": anomaly_rows,
            "timeline": event_timeline,
            "comparison_summary_markdown": compare_summary_markdown,
            "comparison_summary_relpath": _safe_relpath(fixture.summary, repo),
        },
        "transactions": transaction_surface,
        "snapshots_available": sorted(snapshots.keys()),
    }


    return {
        "date": date,
        "fixture": {
            "date": date,
            "comparison_dir": str(fixture.comparison_dir),
            "comparison_relpath": _safe_relpath(fixture.comparison_dir, repo),
            "baseline_bundle_dir": str(fixture.baseline_dir),
            "baseline_bundle_relpath": _safe_relpath(fixture.baseline_dir, repo),
            "candidate_bundle_dir": str(fixture.candidate_dir),
            "candidate_bundle_relpath": _safe_relpath(fixture.candidate_dir, repo),
            "truth_contract": {
                "topology_changed": False,
                "opening_fixture_set": ["20260306", "20260310", "20260312"],
                "hero_day": "20260312",
                "note": (
                    "The Mission Control demo contract was truthfully recut to the March fixtures that are "
                    "actually committed in this worktree."
                ),
            },
        },
        "daily_summary": daily_summary,
        "strategy_card_summaries": all_cards,
        "anomalies": anomaly_rows,
        "event_timeline": event_timeline,
        "transaction_surface": transaction_surface,
        "compare": compare,
        "snapshots": snapshots,
        "deck_view": deck_view,
    }



def build_card_detail(
    date: str,
    lane: str,
    card_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    repo = root or repo_root()
    fixture = _resolve_fixture(date, repo)

    if lane == "baseline-bot":
        bundle_dir = fixture.baseline_dir
    elif lane == "steamer-card-engine":
        bundle_dir = fixture.candidate_dir
    else:
        raise DashboardDataError(f"unknown lane: {lane}")

    run_manifest = _load_json(bundle_dir / "run-manifest.json")
    scenario_spec = _load_json(bundle_dir / "scenario-spec.json")
    config_snapshot = _load_json(bundle_dir / "config-snapshot.json")
    anomalies = _load_json(bundle_dir / "anomalies.json").get("anomalies", [])

    intents = _load_jsonl(bundle_dir / "intent-log.jsonl")
    risks = _load_jsonl(bundle_dir / "risk-receipts.jsonl")
    executions = _load_jsonl(bundle_dir / "execution-log.jsonl")
    features = _load_jsonl(bundle_dir / "feature-provenance.jsonl")

    card_intents = [row for row in intents if row.get("card_id") == card_id]
    if not card_intents:
        raise DashboardDataError(f"unknown card_id for lane {lane}: {card_id}")

    card_intents.sort(key=lambda row: (row.get("intent_time_utc", ""), row.get("intent_id", "")))

    deck_id = card_intents[0].get("deck_id") or config_snapshot.get("deck_id")
    card_version = card_intents[0].get("card_version", "unknown")
    deck_version = config_snapshot.get("deck_version")

    symbols = Counter(row.get("symbol", "unknown") for row in card_intents)
    sides = Counter(row.get("side", "unknown") for row in card_intents)
    intent_reasons = Counter(row.get("reason_code", "unknown") for row in card_intents)

    intent_ids = {row["intent_id"] for row in card_intents if "intent_id" in row}
    card_risks = [row for row in risks if row.get("intent_id") in intent_ids]
    card_risks.sort(key=lambda row: (row.get("decision_time_utc", ""), row.get("risk_decision_id", "")))

    risk_reason = Counter(row.get("reason_code", "unknown") for row in card_risks)
    allowed = sum(1 for row in card_risks if row.get("decision") == "allow")
    blocked = sum(1 for row in card_risks if row.get("decision") == "block")

    risk_ids = {row.get("risk_decision_id") for row in card_risks if row.get("risk_decision_id")}
    card_exec = [row for row in executions if row.get("risk_decision_id") in risk_ids]
    card_exec.sort(key=lambda row: (row.get("request_time_utc", ""), row.get("exec_request_id", "")))

    card_symbols = {row.get("symbol") for row in card_intents if row.get("symbol")}
    card_features = [row for row in features if row.get("symbol") in card_symbols]
    card_features.sort(key=lambda row: (row.get("computed_at_utc", ""), row.get("feature_record_id", "")))

    qty_requested = [row.get("requested_qty") for row in card_intents if "requested_qty" in row]
    qty_exec = [row.get("qty") for row in card_exec if "qty" in row]

    truth_notes: list[str] = []
    if qty_requested and all(float(qty) == 0.0 for qty in qty_requested if qty is not None):
        truth_notes.append(
            "All intent requested_qty values are 0.0 in the committed March fixtures (placeholder shells)."
        )
    if qty_exec and all(float(qty) == 0.0 for qty in qty_exec if qty is not None):
        truth_notes.append(
            "All execution request qty values are 0.0 in the committed March fixtures (no live fills)."
        )

    return {
        "date": date,
        "lane": lane,
        "card_id": card_id,
        "card_version": card_version,
        "deck_id": deck_id,
        "deck_version": deck_version,
        "config_hash": config_snapshot.get("config_hash"),
        "scenario_id": scenario_spec.get("scenario_id"),
        "run_id": run_manifest.get("run_id"),
        "bundle_relpath": _safe_relpath(bundle_dir, repo),
        "anomaly_refs": [row.get("anomaly_id") for row in anomalies],
        "universe": _universe_surface(scenario_spec),
        "counts": {
            "intents": len(card_intents),
            "risk_decisions": len(card_risks),
            "risk_allow": allowed,
            "risk_block": blocked,
            "execution_requests": len(card_exec),
            "feature_records": len(card_features),
        },
        "distributions": {
            "top_symbols": _top_counter(symbols, limit=8),
            "sides": _top_counter(sides, limit=4),
            "intent_reasons": _top_counter(intent_reasons, limit=10),
            "risk_reasons": _top_counter(risk_reason, limit=10),
        },
        "samples": {
            "intents": _sample_rows(card_intents, sample_size=14),
            "risk_decisions": _sample_rows(card_risks, sample_size=14),
            "execution_requests": _sample_rows(card_exec, sample_size=14),
            "feature_provenance": _sample_rows(card_features, sample_size=12),
        },
        "truth_notes": truth_notes,
    }
