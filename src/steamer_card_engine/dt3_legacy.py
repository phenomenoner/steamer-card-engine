from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from steamer_card_engine.sim_compare import canonical_json_bytes, sha256_file, sha256_hex


DT3_REQUIRED_FILES = ("ticks.jsonl", "decisions.jsonl", "orders.jsonl")
DT3_ARTIFACT_FILES = [
    "run-manifest.json",
    "scenario-spec.json",
    "event-log.jsonl",
    "feature-provenance.jsonl",
    "intent-log.jsonl",
    "risk-receipts.jsonl",
    "execution-log.jsonl",
    "order-lifecycle.jsonl",
    "fills.jsonl",
    "positions.jsonl",
    "pnl-summary.json",
    "anomalies.json",
    "config-snapshot.json",
    "dt3-contract.json",
    "file-index.json",
]


def _now_utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _jsonl_iter(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"expected JSON object in {path} line {line_no}")
            yield line_no, payload


def _parse_ts(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        value = float(text)
    if isinstance(value, (int, float)):
        numeric = float(value)
        abs_numeric = abs(numeric)
        if abs_numeric >= 1e18:
            numeric /= 1e9
        elif abs_numeric >= 1e15:
            numeric /= 1e6
        elif abs_numeric >= 1e12:
            numeric /= 1e3
        return datetime.fromtimestamp(numeric, tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return None


def _parse_dt3_blob(text: Any) -> dict[str, str]:
    raw = str(text or "")
    out: dict[str, str] = {}
    for key in [
        "buy_sell",
        "price_type",
        "quantity",
        "time_in_force",
        "order_type",
        "last_time",
        "error_message",
        "order_no",
        "seq_no",
        "stock_no",
        "user_def",
        "filled_avg_price",
        "filled_qty",
        "filled_price",
        "filled_time",
        "account",
    ]:
        match = re.search(rf"{key}: (?:(\"[^\"]+\")|([^,\n]+))", raw)
        if match:
            out[key] = (match.group(1) or match.group(2)).strip().strip('"')
    return out


def _side_from_buy_sell(value: str | None, *, action: str | None = None) -> str:
    normalized = (value or "").strip().lower()
    action_norm = (action or "").strip().lower()
    if normalized == "sell":
        return "sell" if action_norm != "exit" else "buy"
    if normalized == "buy":
        return "buy" if action_norm != "exit" else "cover"
    return "sell" if action_norm == "enter" else "buy"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())



def _parse_lot_limits(source_dir: Path) -> dict[str, float]:
    limits: dict[str, float] = {}
    for log_path in sorted(source_dir.glob("nohup*.log")):
        with log_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                match = re.search(r"Symbol (\d+)'s lot limit: ([-+]?\d+(?:\.\d+)?)", line)
                if match:
                    limits[match.group(1)] = float(match.group(2))
    return limits

def extract_dt3_contract(source_dir: Path) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    for name in DT3_REQUIRED_FILES:
        if not (source_dir / name).exists():
            raise FileNotFoundError(f"missing DT3 source file: {source_dir / name}")

    decisions: list[dict[str, Any]] = []
    enter_like: list[dict[str, Any]] = []
    symbols: set[str] = set()
    reason_counts: dict[str, int] = {}
    for line_no, row in _jsonl_iter(source_dir / "decisions.jsonl"):
        symbol = str(row.get("symbol") or "")
        if symbol:
            symbols.add(symbol)
        reason = str(row.get("reason"))
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
        state = row.get("state") if isinstance(row.get("state"), dict) else {}
        item = {
            "line_no": line_no,
            "symbol": symbol,
            "gate": row.get("gate"),
            "enter": bool(row.get("enter")),
            "reason": row.get("reason"),
            "time": row.get("time"),
            "state": state,
        }
        decisions.append(item)
        if row.get("enter") is True or row.get("reason") == "enter_rev_short":
            enter_like.append(item)

    order_events: list[dict[str, Any]] = []
    for line_no, row in _jsonl_iter(source_dir / "orders.jsonl"):
        parsed = _parse_dt3_blob(row.get("data"))
        item = {
            "line_no": line_no,
            "event": row.get("event"),
            "symbol": str(row.get("symbol") or parsed.get("stock_no") or ""),
            "time": row.get("time"),
            "time_utc": _parse_ts(row.get("time")),
            "user_def": row.get("user_def") or parsed.get("user_def"),
            "status": row.get("status"),
            "action": row.get("action"),
            "parsed": parsed,
            "raw": row,
        }
        for key in ("entry_price", "exit_price", "qty", "pnl", "duration"):
            if key in row:
                item[key] = row.get(key)
        order_events.append(item)

    def is_entry_event(item: dict[str, Any]) -> bool:
        return item.get("action") == "enter" or str(item.get("user_def") or "").endswith("Enter")

    def is_exit_event(item: dict[str, Any]) -> bool:
        user_def = str(item.get("user_def") or "")
        action = str(item.get("action") or "")
        return (not is_entry_event(item)) and (
            action in {"exit", "stop", "closure"}
            or user_def.endswith(("Stop", "Exit", "Closure", "Close"))
        )

    first_submit = next((o for o in order_events if o["event"] == "order_submit" and is_entry_event(o)), None)
    first_entry_fill = next((o for o in order_events if o["event"] == "order_fill" and is_entry_event(o)), None)
    first_exit_submit = next((o for o in order_events if o["event"] == "order_submit" and is_exit_event(o)), None)
    first_exit_fill = next((o for o in order_events if o["event"] == "order_fill" and is_exit_event(o)), None)
    trade_summary = next((o for o in order_events if o["event"] == "trade_summary"), None)
    selected_symbol = (first_submit or first_entry_fill or (enter_like[0] if enter_like else {})).get("symbol")

    first_enter_like = enter_like[0] if enter_like else None
    lot_limits = _parse_lot_limits(source_dir)
    first_executable_enter_like = next(
        (item for item in enter_like if lot_limits.get(str(item.get("symbol") or ""), 0.0) > 0),
        None,
    )

    return {
        "schema": "dt3_legacy_contract_v1",
        "source_dir": str(source_dir),
        "source_checksums": {
            name: sha256_file(source_dir / name)
            for name in DT3_REQUIRED_FILES
            if (source_dir / name).exists()
        },
        "raw_counts": {
            "ticks": _line_count(source_dir / "ticks.jsonl"),
            "decisions": len(decisions),
            "orders": len(order_events),
            "enter_like": len(enter_like),
        },
        "symbols": sorted(symbols),
        "lot_limits": lot_limits,
        "reason_top": sorted(reason_counts.items(), key=lambda kv: kv[1], reverse=True)[:20],
        "legacy_online_contract": {
            "position_gate": "first_successful_entry_only",
            "selected_symbol": selected_symbol,
            "decision_first_enter_symbol": first_enter_like.get("symbol") if first_enter_like else None,
            "executable_decision_first_symbol": first_executable_enter_like.get("symbol") if first_executable_enter_like else None,
            "order_first_entry_symbol": selected_symbol,
            "first_entry_gate_ok": bool(first_submit and first_entry_fill and selected_symbol),
            "suppressed_enter_like_count": max(0, len(enter_like) - (1 if selected_symbol else 0)),
            "counterfactual_no_gate_would_emit": len(enter_like),
        },
        "first_submit": first_submit,
        "first_entry_fill": first_entry_fill,
        "first_exit_submit": first_exit_submit,
        "first_exit_fill": first_exit_fill,
        "trade_summary": trade_summary,
    }


def _build_scenario_spec(*, scenario_id: str, session_date: str, contract: dict[str, Any], source_dir: Path) -> dict[str, Any]:
    checksums = contract["source_checksums"]
    source_id = "dt3-legacy:" + hashlib.sha256(
        canonical_json_bytes({"source_dir_name": source_dir.name, "checksums": checksums})
    ).hexdigest()[:24]
    return {
        "scenario_spec_version": "scenario-spec/v1",
        "scenario_id": scenario_id,
        "symbol_set": {
            "mode": "explicit-list",
            "symbols": contract["symbols"],
            "symbol_set_id": f"dt3-legacy-symbols:{session_date}",
        },
        "session_slice": {
            "session_date": session_date,
            "slice_label": "full-session",
            "start_local": "09:00:00",
            "end_local": "13:30:00",
        },
        "event_source": {
            "source_id": source_id,
            "source_kind": "recorded-stream",
            "source_ref": str(source_dir),
            "adjustment_mode": "raw",
        },
        "market_clock": {"timezone": "Asia/Taipei", "calendar": "TWSE"},
        "execution_model": {
            "fee_model": "legacy-fee-model-v0",
            "tax_model": "legacy-tax-model-v0",
            "slippage_model": "legacy-slippage-unknown",
            "rounding_rule": "legacy-rounding-unknown",
            "fill_model": "sim-fill-v1",
        },
        "determinism": {
            "mode": "best-effort",
            "random_seed": None,
            "notes": "DT3 legacy archived ticks/orders replay; broker disabled",
        },
    }


def normalize_dt3_legacy_bundle(
    *,
    source_dir: Path,
    output_dir: Path,
    session_date: str,
    scenario_id: str,
    run_id: str,
    lane: str = "baseline-bot",
    deck_id: str = "dt3-legacy-deck",
    card_id: str = "dt3-legacy-rev-short-card",
    card_version: str = "legacy/v0",
    run_type: str = "replay-sim",
    intent_source: str = "order-first",
) -> dict[str, Any]:
    source_dir = source_dir.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    contract = extract_dt3_contract(source_dir)
    scenario_spec = _build_scenario_spec(
        scenario_id=scenario_id,
        session_date=session_date,
        contract=contract,
        source_dir=source_dir,
    )
    scenario_fingerprint = sha256_hex(canonical_json_bytes(scenario_spec))

    event_rows: list[dict[str, Any]] = []
    min_ts: str | None = None
    max_ts: str | None = None
    for idx, (_line_no, row) in enumerate(_jsonl_iter(source_dir / "ticks.jsonl"), start=1):
        ts = _parse_ts(row.get("event_time_utc") or row.get("received_at_utc") or row.get("time")) or _now_utc_iso()
        min_ts = ts if min_ts is None or ts < min_ts else min_ts
        max_ts = ts if max_ts is None or ts > max_ts else max_ts
        event_rows.append(
            {
                "seq_no": idx,
                "event_id": str(row.get("event_id") or row.get("raw_id") or f"dt3-tick-{idx:08d}"),
                "event_time_utc": ts,
                "symbol": str(row.get("symbol") or "UNKNOWN"),
                "event_type": str(row.get("event_type") or row.get("raw_event") or "market_tick"),
                "payload": row,
            }
        )

    contract_selected = contract["legacy_online_contract"].get("selected_symbol")
    decision_selected = contract["legacy_online_contract"].get("decision_first_enter_symbol")
    executable_decision_selected = contract["legacy_online_contract"].get("executable_decision_first_symbol")
    if intent_source not in {"order-first", "decision-first", "executable-decision-first"}:
        raise ValueError(f"unsupported DT3 intent_source: {intent_source}")
    if intent_source == "decision-first":
        selected = decision_selected
    elif intent_source == "executable-decision-first":
        selected = executable_decision_selected
    else:
        selected = contract_selected
    contract["legacy_online_contract"]["selected_symbol"] = selected
    contract["legacy_online_contract"]["intent_source"] = intent_source
    contract["legacy_online_contract"]["order_decision_symbol_match"] = (
        contract_selected == selected
    )
    first_submit = contract.get("first_submit") or {}
    first_entry_fill = contract.get("first_entry_fill") or {}
    first_exit_fill = contract.get("first_exit_fill") or {}
    trade_summary = contract.get("trade_summary") or {}
    submit_parsed = first_submit.get("parsed") or {}
    entry_parsed = first_entry_fill.get("parsed") or {}
    exit_parsed = first_exit_fill.get("parsed") or {}

    entry_qty = float(entry_parsed.get("filled_qty") or submit_parsed.get("quantity") or trade_summary.get("qty") or 0)
    entry_price = float(entry_parsed.get("filled_price") or trade_summary.get("entry_price") or 0)
    exit_qty = float(exit_parsed.get("filled_qty") or trade_summary.get("qty") or 0)
    exit_price = float(exit_parsed.get("filled_price") or trade_summary.get("exit_price") or 0)
    realized = float(trade_summary.get("pnl") or 0.0)
    position_id = f"dt3-position-{session_date}-{selected or 'unknown'}"
    order_id_entry = str(first_submit.get("order_no") or submit_parsed.get("order_no") or "dt3-entry-order")
    order_id_exit = str((contract.get("first_exit_submit") or {}).get("order_no") or exit_parsed.get("order_no") or "dt3-exit-order")
    side = _side_from_buy_sell(submit_parsed.get("buy_sell"), action="enter")

    feature_rows = []
    intent_rows = []
    risk_rows = []
    execution_rows = []
    lifecycle_rows = []
    fill_rows = []
    position_rows = []
    anomalies: list[dict[str, Any]] = []

    def anomaly(severity: str, category: str, message: str) -> None:
        anomalies.append(
            {
                "anomaly_id": f"anom-{len(anomalies)+1:04d}",
                "severity": severity,
                "category": category,
                "message": message,
                "related_ids": [],
                "detected_at_utc": _now_utc_iso(),
            }
        )

    if not contract["legacy_online_contract"].get("first_entry_gate_ok"):
        anomaly("major", "dt3-first-entry-incomplete", "DT3 first successful entry submit/fill could not be fully identified.")

    if selected and contract_selected and contract_selected != selected:
        anomaly("critical", "dt3-order-decision-symbol-mismatch", f"order-first symbol {contract_selected} differs from selected {intent_source} symbol {selected}")

    if selected:
        feature_rows.append(
            {
                "feature_record_id": "dt3-contract-feature-0001",
                "event_id": "dt3-contract-first-entry",
                "symbol": selected,
                "feature_name": "dt3.legacy.first_entry_contract",
                "feature_version": "dt3-legacy/v1",
                "window_spec": "full-session decisions/orders",
                "value_hash": sha256_hex(canonical_json_bytes(contract["legacy_online_contract"])),
                "computed_at_utc": first_submit.get("time_utc") or _now_utc_iso(),
            }
        )
        intent_id = f"intent-dt3-{session_date}-{selected}-entry"
        risk_id = f"risk-dt3-{session_date}-{selected}-entry"
        exec_id = f"exec-dt3-{session_date}-{selected}-entry"
        intent_rows.append(
            {
                "intent_id": intent_id,
                "event_id": "dt3-contract-first-entry",
                "intent_time_utc": first_submit.get("time_utc") or first_entry_fill.get("time_utc") or _now_utc_iso(),
                "card_id": card_id,
                "card_version": card_version,
                "deck_id": deck_id,
                "symbol": selected,
                "side": side,
                "requested_qty": entry_qty,
                "reason_code": "legacy_dt3_first_successful_entry_only",
            }
        )
        risk_rows.append(
            {
                "risk_decision_id": risk_id,
                "intent_id": intent_id,
                "decision_time_utc": first_submit.get("time_utc") or _now_utc_iso(),
                "decision": "allow",
                "policy_scope": "deck",
                "policy_name": "dt3_first_successful_entry_only",
                "reason_code": "first_entry_selected",
                "adjusted_qty": entry_qty,
            }
        )
        execution_rows.append(
            {
                "exec_request_id": exec_id,
                "risk_decision_id": risk_id,
                "request_time_utc": first_submit.get("time_utc") or _now_utc_iso(),
                "symbol": selected,
                "side": side,
                "order_type": submit_parsed.get("price_type") or "market",
                "qty": entry_qty,
                "limit_price": None,
            }
        )
        if first_submit:
            lifecycle_rows.append(
                {
                    "lifecycle_event_id": f"lifecycle-{order_id_entry}-ack",
                    "exec_request_id": exec_id,
                    "order_id": order_id_entry,
                    "event_time_utc": first_submit.get("time_utc") or _now_utc_iso(),
                    "state": "ack" if str(first_submit.get("status")) == "10" else "new",
                    "cum_qty": 0.0,
                    "leaves_qty": entry_qty,
                    "last_fill_qty": None,
                    "last_fill_price": None,
                    "reason_code": "dt3_order_submit",
                }
            )
        if first_entry_fill:
            lifecycle_rows.append(
                {
                    "lifecycle_event_id": f"lifecycle-{order_id_entry}-filled",
                    "exec_request_id": exec_id,
                    "order_id": order_id_entry,
                    "event_time_utc": first_entry_fill.get("time_utc") or _now_utc_iso(),
                    "state": "filled",
                    "cum_qty": entry_qty,
                    "leaves_qty": 0.0,
                    "last_fill_qty": entry_qty,
                    "last_fill_price": entry_price,
                    "reason_code": "dt3_entry_fill",
                }
            )
            fill_rows.append(
                {
                    "fill_id": f"fill-{order_id_entry}-entry",
                    "order_id": order_id_entry,
                    "position_id": position_id,
                    "fill_time_utc": first_entry_fill.get("time_utc") or _now_utc_iso(),
                    "symbol": selected,
                    "side": side,
                    "qty": entry_qty,
                    "price": entry_price,
                    "fee_amount": 0.0,
                    "tax_amount": 0.0,
                }
            )
            position_rows.append(
                {
                    "position_event_id": f"position-{selected}-open",
                    "position_id": position_id,
                    "event_time_utc": first_entry_fill.get("time_utc") or _now_utc_iso(),
                    "symbol": selected,
                    "net_qty": -entry_qty if side == "sell" else entry_qty,
                    "avg_cost": entry_price,
                    "position_state": "open",
                    "exit_reason": None,
                    "realized_pnl_gross": 0.0,
                    "realized_pnl_net": 0.0,
                }
            )
        if first_exit_fill:
            exit_exec_id = f"exec-dt3-{session_date}-{selected}-exit"
            lifecycle_rows.append(
                {
                    "lifecycle_event_id": f"lifecycle-{order_id_exit}-filled",
                    "exec_request_id": exit_exec_id,
                    "order_id": order_id_exit,
                    "event_time_utc": first_exit_fill.get("time_utc") or _now_utc_iso(),
                    "state": "filled",
                    "cum_qty": exit_qty,
                    "leaves_qty": 0.0,
                    "last_fill_qty": exit_qty,
                    "last_fill_price": exit_price,
                    "reason_code": "dt3_exit_fill",
                }
            )
            fill_rows.append(
                {
                    "fill_id": f"fill-{order_id_exit}-exit",
                    "order_id": order_id_exit,
                    "position_id": position_id,
                    "fill_time_utc": first_exit_fill.get("time_utc") or _now_utc_iso(),
                    "symbol": selected,
                    "side": "buy" if side == "sell" else "sell",
                    "qty": exit_qty,
                    "price": exit_price,
                    "fee_amount": 0.0,
                    "tax_amount": 0.0,
                }
            )
            position_rows.append(
                {
                    "position_event_id": f"position-{selected}-closed",
                    "position_id": position_id,
                    "event_time_utc": first_exit_fill.get("time_utc") or _now_utc_iso(),
                    "symbol": selected,
                    "net_qty": 0.0,
                    "avg_cost": entry_price,
                    "position_state": "closed",
                    "exit_reason": "dt3_legacy_exit",
                    "realized_pnl_gross": realized,
                    "realized_pnl_net": realized,
                }
            )

    _append_jsonl(output_dir / "event-log.jsonl", event_rows)
    _append_jsonl(output_dir / "feature-provenance.jsonl", feature_rows)
    _append_jsonl(output_dir / "intent-log.jsonl", intent_rows)
    _append_jsonl(output_dir / "risk-receipts.jsonl", risk_rows)
    _append_jsonl(output_dir / "execution-log.jsonl", execution_rows)
    _append_jsonl(output_dir / "order-lifecycle.jsonl", lifecycle_rows)
    _append_jsonl(output_dir / "fills.jsonl", fill_rows)
    _append_jsonl(output_dir / "positions.jsonl", position_rows)

    pnl_summary = {
        "currency": "TWD",
        "realized_pnl_gross": realized,
        "fees_total": 0.0,
        "taxes_total": 0.0,
        "realized_pnl_net": realized,
        "entry_count": 1 if entry_qty else 0,
        "exit_count": 1 if exit_qty else 0,
        "exit_reason_counts": {"dt3_legacy_exit": 1} if exit_qty else {},
        "win_count": 1 if realized > 0 else 0,
        "loss_count": 1 if realized < 0 else 0,
        "max_position_qty": entry_qty,
        "per_symbol_totals": {selected: realized} if selected else {},
        "entry_signal_count": contract["raw_counts"]["enter_like"],
        "suppressed_entry_signal_count": contract["legacy_online_contract"]["suppressed_enter_like_count"],
    }
    _write_json(output_dir / "pnl-summary.json", pnl_summary)
    _write_json(output_dir / "anomalies.json", {"anomalies": anomalies})
    _write_json(output_dir / "dt3-contract.json", contract)
    _write_json(output_dir / "scenario-spec.json", scenario_spec)

    execution_model = {
        "fee_model": "legacy-fee-model-v0",
        "tax_model": "legacy-tax-model-v0",
        "slippage_model": "legacy-slippage-unknown",
        "rounding_rule": "legacy-rounding-unknown",
        "fill_model": "sim-fill-v1",
        "random_seed": None,
    }
    run_manifest = {
        "schema_version": "sim-artifacts/v1",
        "run_id": run_id,
        "lane": lane,
        "run_type": run_type,
        "scenario_id": scenario_id,
        "scenario_spec_version": scenario_spec["scenario_spec_version"],
        "scenario_fingerprint": scenario_fingerprint,
        "session_date": session_date,
        "started_at_utc": min_ts or _now_utc_iso(),
        "ended_at_utc": max_ts or _now_utc_iso(),
        "status": "partial" if anomalies else "success",
        "provenance": {
            "engine_name": "steamer-card-engine-dt3-legacy-adapter",
            "engine_git_sha": "unknown",
            "dependency_lock_hash": "unknown",
            "config_hash": sha256_hex(canonical_json_bytes({"contract": contract["legacy_online_contract"], "lane": lane})),
            "python_version": __import__("sys").version.split()[0],
        },
        "market_event_source": {
            "source_id": scenario_spec["event_source"]["source_id"],
            "source_kind": "recorded-stream",
            "source_ref": str(source_dir),
            "timezone": "Asia/Taipei",
            "calendar": "TWSE",
            "time_range": {"start": min_ts, "end": max_ts},
            "adjustment_mode": "raw",
        },
        "execution_model": execution_model,
        "capability_posture": {
            "market_data_enabled": True,
            "trade_enabled": False,
            "account_query_enabled": False,
        },
        "artifact_files": DT3_ARTIFACT_FILES,
    }
    _write_json(output_dir / "run-manifest.json", run_manifest)
    _write_json(
        output_dir / "config-snapshot.json",
        {
            "scenario_id": scenario_id,
            "deck_id": deck_id,
            "deck_version": "dt3-legacy/v1",
            "cards": [{"card_id": card_id, "card_version": card_version}],
            "global_config_version": "dt3-legacy-replay/v1",
            "config_hash": run_manifest["provenance"]["config_hash"],
            "adapter": {"name": "dt3_legacy", "version": "v1", "source_dir": str(source_dir)},
        },
    )

    file_entries = []
    for name in DT3_ARTIFACT_FILES:
        if name == "file-index.json":
            continue
        path = output_dir / name
        if path.exists():
            file_entries.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    _write_json(
        output_dir / "file-index.json",
        {
            "schema_version": "sim-artifacts/v1",
            "run_id": run_id,
            "generated_at_utc": _now_utc_iso(),
            "files": file_entries,
            "notes": ["file-index.json self-hash is intentionally omitted"],
        },
    )

    return {
        "bundle_dir": str(output_dir),
        "run_id": run_id,
        "scenario_id": scenario_id,
        "scenario_fingerprint": scenario_fingerprint,
        "lane": lane,
        "counts": {
            "events": len(event_rows),
            "features": len(feature_rows),
            "intents": len(intent_rows),
            "risk_receipts": len(risk_rows),
            "execution_requests": len(execution_rows),
            "order_lifecycle": len(lifecycle_rows),
            "fills": len(fill_rows),
            "positions": len(position_rows),
            "anomalies": len(anomalies),
        },
        "dt3_contract": contract["legacy_online_contract"],
        "pnl_summary": pnl_summary,
    }
