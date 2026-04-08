from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from .session_phase import (
    TWSE_TIMEZONE,
    append_phase_transition,
    assess_twse_session_phase,
    build_twse_phase_contract,
    parse_utc_timestamp,
)


BUNDLE_REQUIRED_FILES = [
    "run-manifest.json",
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
    "file-index.json",
]

ALLOWED_SIM_FILL_MODELS = {"sim-fill-v1"}


class SimCompareError(ValueError):
    pass


@dataclass(slots=True)
class BundleValidationResult:
    bundle_dir: Path
    manifest: dict[str, Any]
    errors: list[str]
    warnings: list[str]
    counts: dict[str, int]
    anomalies_by_severity: dict[str, int]
    execution_model_hash: str


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _parse_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _parse_timestamp_to_utc(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            numeric = float(text)
        else:
            text = text.replace("Z", "+00:00")
            try:
                parsed = datetime.fromisoformat(text)
            except ValueError:
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            else:
                parsed = parsed.astimezone(UTC)
            return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    else:
        return None

    abs_numeric = abs(numeric)
    if abs_numeric >= 1e18:
        seconds = numeric / 1e9
    elif abs_numeric >= 1e15:
        seconds = numeric / 1e6
    elif abs_numeric >= 1e12:
        seconds = numeric / 1e3
    else:
        seconds = numeric

    try:
        parsed = datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    return parsed.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _jsonl_iter(path: Path):
    with path.open("r", encoding="utf-8") as file:
        for line_no, line in enumerate(file, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as error:
                raise SimCompareError(f"invalid JSONL in {path} line {line_no}: {error}") from error
            if not isinstance(payload, dict):
                raise SimCompareError(f"expected JSON object in {path} line {line_no}")
            yield line_no, payload


def _select_event_sources(baseline_dir: Path) -> list[Path]:
    ticks = baseline_dir / "ticks.jsonl"
    if ticks.exists():
        return [ticks]

    dashboard = _parse_json(baseline_dir / "dashboard.json", default={})
    if isinstance(dashboard, dict):
        inputs = dashboard.get("inputs")
        if isinstance(inputs, dict):
            files = inputs.get("trades_jsonl_files")
            if isinstance(files, list):
                resolved: list[Path] = []
                for item in files:
                    if not isinstance(item, str):
                        continue
                    source = Path(item)
                    if not source.is_absolute():
                        source = (baseline_dir / source).resolve()
                    if source.exists():
                        resolved.append(source)
                if resolved:
                    return resolved
    return []


def _decision_key(row: dict[str, Any], *, line_no: int) -> str:
    symbol = str(row.get("symbol") or "UNKNOWN")
    side = str(row.get("side") or "unknown")
    ts = str(row.get("ts") or row.get("time") or f"line-{line_no}")
    return f"{symbol}:{side}:{ts}"


def _map_side(side: str) -> str | None:
    lowered = side.strip().lower()
    mapping = {
        "long": "buy",
        "short": "sell",
        "buy": "buy",
        "sell": "sell",
        "cover": "buy",
        "reduce": "sell",
        "exit": "sell",
    }
    return mapping.get(lowered)


def _hash_text(value: str) -> str:
    return sha256_hex(value.encode("utf-8"))


def _time_in_force_for_profile(profile_name: str | None) -> str | None:
    if profile_name is None:
        return None
    if profile_name.endswith("-rod"):
        return "ROD"
    if profile_name.endswith("-ioc"):
        return "IOC"
    return None


def _event_observation_state(
    row: dict[str, Any], event_type: str, phase: str | None
) -> str | None:
    payload = row if isinstance(row, dict) else {}
    is_trial = payload.get("isTrial")
    volume = payload.get("volume")

    if is_trial is True:
        return "trial-match"
    if phase == "regular_session_open" and event_type in {"trade", "session"}:
        return "official-open-signal"
    if phase == "regular_session_open" and is_trial is False:
        return "official-open-print"
    if phase == "regular_session_open":
        return "open-discovery"
    if phase in {"regular_session", "risk_monitor_only", "forced_exit", "final_auction"}:
        if is_trial is False or (is_trial is None and volume not in (None, 0)):
            return "regular-market"
    return None


def _build_execution_payload(
    *,
    exec_request_id: str,
    risk_decision_id: str,
    decision_ts: str,
    symbol: str,
    side: str,
    phase_assessment: Any,
) -> dict[str, Any]:
    profile_name = phase_assessment.default_order_profile if phase_assessment else None
    return {
        "exec_request_id": exec_request_id,
        "risk_decision_id": risk_decision_id,
        "request_time_utc": decision_ts,
        "symbol": symbol,
        "side": side,
        "order_type": "market",
        "time_in_force": _time_in_force_for_profile(profile_name),
        "market_phase": phase_assessment.phase if phase_assessment else None,
        "phase_semantic_label": (
            phase_assessment.semantic_label if phase_assessment else None
        ),
        "session_contract_status": (
            phase_assessment.contract_status if phase_assessment else "unknown"
        ),
        "order_profile_name": profile_name,
        "requested_user_def_suffix": (
            phase_assessment.requested_user_def_suffix if phase_assessment else None
        ),
        "qty": 0.0,
        "limit_price": None,
    }


def _build_lifecycle_placeholder(
    *,
    execution_payload: dict[str, Any],
    reason_code: str,
) -> dict[str, Any]:
    exec_request_id = str(execution_payload["exec_request_id"])
    return {
        "lifecycle_event_id": f"lifecycle-{exec_request_id}",
        "exec_request_id": exec_request_id,
        "order_id": f"order-{exec_request_id}",
        "event_time_utc": execution_payload["request_time_utc"],
        "state": "new",
        "cum_qty": 0.0,
        "leaves_qty": float(execution_payload.get("qty") or 0.0),
        "last_fill_qty": None,
        "last_fill_price": None,
        "reason_code": reason_code,
        "market_phase": execution_payload.get("market_phase"),
        "phase_semantic_label": execution_payload.get("phase_semantic_label"),
        "order_profile_name": execution_payload.get("order_profile_name"),
    }


def _write_json(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")


def _line_count(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            if line.strip():
                count += 1
    return count


def normalize_baseline_bundle(
    *,
    baseline_dir: Path,
    output_dir: Path,
    session_date: str,
    scenario_id: str,
    run_type: str = "replay-sim",
    market_event_source_id: str = "legacy-baseline-source",
    market_event_source_kind: str = "recorded-stream",
    market_event_source_ref: str | None = None,
    run_id: str | None = None,
    lane: str = "baseline-bot",
    scenario_spec_path: Path | None = None,
    max_events: int | None = None,
    max_decisions: int | None = None,
    fill_model: str = "sim-fill-v1",
    engine_name: str = "steamer-card-engine-baseline-normalizer",
    emitter_name: str = "steamer-card-engine sim normalize-baseline",
    emitter_version: str = "m1-normalizer/v0",
    determinism_note: str = "derived by baseline normalizer from legacy artifacts",
    config_snapshot_actor_key: str = "normalizer",
) -> dict[str, Any]:
    baseline_dir = baseline_dir.resolve()
    market_event_source_ref = market_event_source_ref or str(baseline_dir)
    output_dir = output_dir.resolve()

    decisions_path = baseline_dir / "decisions.jsonl"
    if not decisions_path.exists():
        raise SimCompareError(f"missing required baseline file: {decisions_path}")

    _ensure_dir(output_dir)

    if run_id is None:
        run_id = f"normalize-{lane}-{session_date}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    anomalies: list[dict[str, Any]] = []
    session_phase_trace = []
    risk_emitted_ids: set[str] = set()
    open_discovery_summary = {
        "saw_trial_match_event": False,
        "saw_official_open_signal": False,
        "first_trial_match_utc": None,
        "first_official_open_signal_utc": None,
    }

    def add_anomaly(severity: str, category: str, message: str, related_ids: list[str] | None = None) -> None:
        anomalies.append(
            {
                "anomaly_id": f"anom-{len(anomalies)+1:04d}",
                "severity": severity,
                "category": category,
                "message": message,
                "related_ids": related_ids or [],
                "detected_at_utc": now_utc_iso(),
            }
        )

    started_at_utc = now_utc_iso()

    event_sources = _select_event_sources(baseline_dir)
    if not event_sources:
        add_anomaly(
            "major",
            "baseline-event-source-missing",
            "No ticks.jsonl or dashboard-referenced trades JSONL files were found. event-log.jsonl will be empty.",
        )

    decisions_total = 0
    event_total = 0
    feature_total = 0
    intent_total = 0
    risk_total = 0
    execution_total = 0
    order_lifecycle_total = 0
    symbols: set[str] = set()
    min_event_time: str | None = None
    max_event_time: str | None = None

    event_log_path = output_dir / "event-log.jsonl"
    feature_path = output_dir / "feature-provenance.jsonl"
    intent_path = output_dir / "intent-log.jsonl"
    risk_path = output_dir / "risk-receipts.jsonl"
    execution_path = output_dir / "execution-log.jsonl"
    lifecycle_path = output_dir / "order-lifecycle.jsonl"
    fills_path = output_dir / "fills.jsonl"
    positions_path = output_dir / "positions.jsonl"

    with (
        event_log_path.open("w", encoding="utf-8") as event_file,
        feature_path.open("w", encoding="utf-8") as feature_file,
        intent_path.open("w", encoding="utf-8") as intent_file,
        risk_path.open("w", encoding="utf-8") as risk_file,
        execution_path.open("w", encoding="utf-8") as execution_file,
        lifecycle_path.open("w", encoding="utf-8") as lifecycle_file,
        fills_path.open("w", encoding="utf-8") as fills_file,
        positions_path.open("w", encoding="utf-8") as positions_file,
    ):
        del fills_file
        del positions_file

        seq_no = 0
        for source in event_sources:
            for line_no, row in _jsonl_iter(source):
                if max_events is not None and event_total >= max_events:
                    add_anomaly(
                        "info",
                        "event-log-truncated",
                        f"event-log truncation applied at max_events={max_events}",
                    )
                    break

                event_time = (
                    _parse_timestamp_to_utc(row.get("event_time_utc"))
                    or _parse_timestamp_to_utc(row.get("received_at_utc"))
                    or _parse_timestamp_to_utc(row.get("time"))
                )
                if event_time is None:
                    event_time = now_utc_iso()

                symbol = str(row.get("symbol") or "UNKNOWN")
                symbols.add(symbol)

                if min_event_time is None or event_time < min_event_time:
                    min_event_time = event_time
                if max_event_time is None or event_time > max_event_time:
                    max_event_time = event_time

                event_id = str(row.get("event_id") or row.get("raw_id") or f"event-{source.stem}-{line_no}")
                event_type = str(row.get("event_type") or row.get("raw_event") or "market_tick")
                phase_assessment = assess_twse_session_phase(event_time)
                append_phase_transition(
                    session_phase_trace,
                    timestamp_utc=event_time,
                    assessment=phase_assessment,
                )

                observation_state = _event_observation_state(
                    row,
                    event_type,
                    phase_assessment.phase if phase_assessment else None,
                )
                if observation_state == "trial-match":
                    open_discovery_summary["saw_trial_match_event"] = True
                    open_discovery_summary["first_trial_match_utc"] = (
                        open_discovery_summary["first_trial_match_utc"] or event_time
                    )
                if observation_state in {"official-open-signal", "official-open-print"}:
                    open_discovery_summary["saw_official_open_signal"] = True
                    open_discovery_summary["first_official_open_signal_utc"] = (
                        open_discovery_summary["first_official_open_signal_utc"] or event_time
                    )

                seq_no += 1
                normalized = {
                    "seq_no": seq_no,
                    "event_id": event_id,
                    "event_time_utc": event_time,
                    "symbol": symbol,
                    "event_type": event_type,
                    "market_phase": phase_assessment.phase if phase_assessment else None,
                    "phase_semantic_label": (
                        phase_assessment.semantic_label if phase_assessment else None
                    ),
                    "session_contract_status": (
                        phase_assessment.contract_status if phase_assessment else "unknown"
                    ),
                    "market_observation_state": observation_state,
                    "payload": row,
                }
                event_file.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                event_total += 1
            if max_events is not None and event_total >= max_events:
                break

        for line_no, row in _jsonl_iter(decisions_path):
            if max_decisions is not None and decisions_total >= max_decisions:
                add_anomaly(
                    "info",
                    "decision-log-truncated",
                    f"decision log truncation applied at max_decisions={max_decisions}",
                )
                break

            decisions_total += 1
            stage = str(row.get("stage") or "unknown")
            reason_code = str(row.get("reason") or "legacy:unknown")
            ok = bool(row.get("ok"))
            symbol = str(row.get("symbol") or "UNKNOWN")
            raw_side = str(row.get("side") or "")
            side = _map_side(raw_side)
            symbols.add(symbol)

            decision_ts = (
                _parse_timestamp_to_utc(row.get("ts"))
                or _parse_timestamp_to_utc(row.get("time"))
                or now_utc_iso()
            )
            phase_assessment = assess_twse_session_phase(decision_ts)
            append_phase_transition(
                session_phase_trace,
                timestamp_utc=decision_ts,
                assessment=phase_assessment,
            )
            if min_event_time is None or decision_ts < min_event_time:
                min_event_time = decision_ts
            if max_event_time is None or decision_ts > max_event_time:
                max_event_time = decision_ts

            key = _decision_key(row, line_no=line_no)
            key_hash = _hash_text(key)
            intent_id = f"intent-{key_hash[:16]}"
            risk_decision_id = f"risk-{key_hash[:16]}"
            exec_request_id = f"exec-{key_hash[:16]}"
            event_id = f"decision-{stage}-{key_hash[:16]}"

            metrics = row.get("metrics")
            if not isinstance(metrics, dict):
                metrics = {}

            if stage == "features":
                feature_payload = {
                    "feature_record_id": f"feature-{line_no:08d}",
                    "event_id": event_id,
                    "symbol": symbol,
                    "feature_name": "legacy.strategy.metrics_snapshot",
                    "feature_version": "legacy/v0",
                    "window_spec": f"bars={metrics.get('bars', 'unknown')}",
                    "value_hash": sha256_hex(canonical_json_bytes(metrics)),
                    "computed_at_utc": decision_ts,
                }
                feature_file.write(json.dumps(feature_payload, ensure_ascii=False) + "\n")
                feature_total += 1

            if stage in {"signal", "entry", "exit", "reduce", "forced_exit", "close", "flatten"}:
                if side is None:
                    add_anomaly(
                        "minor",
                        "decision-unknown-side",
                        f"Unrecognized decision side for stage={stage}: {raw_side!r} (line {line_no}). Intent row skipped.",
                    )
                else:
                    intent_payload = {
                        "intent_id": intent_id,
                        "event_id": event_id,
                        "intent_time_utc": decision_ts,
                        "card_id": "legacy-baseline-card",
                        "card_version": "legacy/v0",
                        "deck_id": "legacy-baseline-deck",
                        "symbol": symbol,
                        "side": side,
                        "requested_qty": 0.0,
                        "reason_code": reason_code,
                        "intent_type": "enter" if stage in {"signal", "entry"} else "exit",
                        "market_phase": phase_assessment.phase if phase_assessment else None,
                        "phase_semantic_label": (
                            phase_assessment.semantic_label if phase_assessment else None
                        ),
                    }
                    intent_file.write(json.dumps(intent_payload, ensure_ascii=False) + "\n")
                    intent_total += 1

            if stage == "gate" or stage in {"exit", "reduce", "forced_exit", "close", "flatten"}:
                if risk_decision_id not in risk_emitted_ids:
                    risk_payload = {
                        "risk_decision_id": risk_decision_id,
                        "intent_id": intent_id,
                        "decision_time_utc": decision_ts,
                        "decision": "allow" if ok else "block",
                        "policy_scope": "global",
                        "policy_name": "legacy_gate" if stage == "gate" else f"legacy_{stage}_policy",
                        "reason_code": reason_code,
                        "adjusted_qty": None if ok else 0.0,
                        "market_phase": phase_assessment.phase if phase_assessment else None,
                        "phase_semantic_label": (
                            phase_assessment.semantic_label if phase_assessment else None
                        ),
                    }
                    risk_file.write(json.dumps(risk_payload, ensure_ascii=False) + "\n")
                    risk_total += 1
                    risk_emitted_ids.add(risk_decision_id)

            if stage in {"entry", "exit", "reduce", "forced_exit", "close", "flatten"} and ok:
                if side is None:
                    add_anomaly(
                        "minor",
                        "execution-skipped-unknown-side",
                        f"{stage} execution skipped due to unknown side {raw_side!r} (line {line_no}).",
                    )
                elif stage == "entry":
                    if phase_assessment is not None and not phase_assessment.allows_regular_entry:
                        add_anomaly(
                            "major",
                            "entry-phase-blocked",
                            (
                                "Entry execution request suppressed because the decision fell outside the "
                                f"generalized regular-session entry window (phase={phase_assessment.phase}, "
                                f"local_time={phase_assessment.local_time}, line={line_no})."
                            ),
                            related_ids=[intent_id, risk_decision_id, exec_request_id],
                        )
                    else:
                        execution_payload = _build_execution_payload(
                            exec_request_id=exec_request_id,
                            risk_decision_id=risk_decision_id,
                            decision_ts=decision_ts,
                            symbol=symbol,
                            side=side,
                            phase_assessment=phase_assessment,
                        )
                        execution_file.write(json.dumps(execution_payload, ensure_ascii=False) + "\n")
                        lifecycle_payload = _build_lifecycle_placeholder(
                            execution_payload=execution_payload,
                            reason_code=reason_code,
                        )
                        lifecycle_file.write(json.dumps(lifecycle_payload, ensure_ascii=False) + "\n")
                        execution_total += 1
                        order_lifecycle_total += 1
                elif stage in {"exit", "reduce"}:
                    if phase_assessment is not None and phase_assessment.allows_exit_monitoring:
                        execution_payload = _build_execution_payload(
                            exec_request_id=exec_request_id,
                            risk_decision_id=risk_decision_id,
                            decision_ts=decision_ts,
                            symbol=symbol,
                            side=side,
                            phase_assessment=phase_assessment,
                        )
                        execution_file.write(json.dumps(execution_payload, ensure_ascii=False) + "\n")
                        lifecycle_payload = _build_lifecycle_placeholder(
                            execution_payload=execution_payload,
                            reason_code=reason_code,
                        )
                        lifecycle_file.write(json.dumps(lifecycle_payload, ensure_ascii=False) + "\n")
                        execution_total += 1
                        order_lifecycle_total += 1
                    else:
                        add_anomaly(
                            "major",
                            "exit-phase-blocked",
                            (
                                f"{stage} execution request suppressed because exit monitoring is not active "
                                f"(phase={phase_assessment.phase if phase_assessment else 'unknown'}, line={line_no})."
                            ),
                            related_ids=[intent_id, risk_decision_id, exec_request_id],
                        )
                else:
                    if phase_assessment is not None and phase_assessment.forced_exit_active:
                        execution_payload = _build_execution_payload(
                            exec_request_id=exec_request_id,
                            risk_decision_id=risk_decision_id,
                            decision_ts=decision_ts,
                            symbol=symbol,
                            side=side,
                            phase_assessment=phase_assessment,
                        )
                        execution_file.write(json.dumps(execution_payload, ensure_ascii=False) + "\n")
                        lifecycle_payload = _build_lifecycle_placeholder(
                            execution_payload=execution_payload,
                            reason_code=reason_code,
                        )
                        lifecycle_file.write(json.dumps(lifecycle_payload, ensure_ascii=False) + "\n")
                        execution_total += 1
                        order_lifecycle_total += 1
                    else:
                        add_anomaly(
                            "major",
                            "forced-exit-phase-blocked",
                            (
                                f"{stage} execution request suppressed because forced-exit is not active "
                                f"(phase={phase_assessment.phase if phase_assessment else 'unknown'}, line={line_no})."
                            ),
                            related_ids=[intent_id, risk_decision_id, exec_request_id],
                        )

        orders_path = baseline_dir / "orders.jsonl"
        if orders_path.exists():
            for line_no, row in _jsonl_iter(orders_path):
                order_id = str(row.get("order_id") or f"legacy-order-{line_no}")
                lifecycle_payload = {
                    "lifecycle_event_id": str(
                        row.get("lifecycle_event_id") or f"lifecycle-{line_no:08d}"
                    ),
                    "exec_request_id": str(row.get("exec_request_id") or "legacy-exec-unknown"),
                    "order_id": order_id,
                    "event_time_utc": (
                        _parse_timestamp_to_utc(row.get("event_time_utc"))
                        or _parse_timestamp_to_utc(row.get("ts"))
                        or now_utc_iso()
                    ),
                    "state": str(row.get("state") or row.get("status") or "new"),
                    "cum_qty": float(row.get("cum_qty") or 0.0),
                    "leaves_qty": float(row.get("leaves_qty") or 0.0),
                    "last_fill_qty": row.get("last_fill_qty"),
                    "last_fill_price": row.get("last_fill_price"),
                    "reason_code": row.get("reason_code"),
                }
                lifecycle_file.write(json.dumps(lifecycle_payload, ensure_ascii=False) + "\n")
                order_lifecycle_total += 1
        else:
            add_anomaly(
                "minor",
                "baseline-orders-missing",
                "orders.jsonl not found; order-lifecycle/fills/positions emitted as placeholders.",
            )

    if not symbols:
        add_anomaly("major", "baseline-symbols-empty", "No symbols discovered from baseline artifacts.")

    execution_model = {
        "fee_model": "legacy-fee-model-v0",
        "tax_model": "legacy-tax-model-v0",
        "slippage_model": "legacy-slippage-unknown",
        "rounding_rule": "legacy-rounding-unknown",
        "fill_model": fill_model,
        "random_seed": None,
    }

    session_phase_contract = build_twse_phase_contract()

    if scenario_spec_path is not None:
        scenario_spec = _parse_json(scenario_spec_path)
        if not isinstance(scenario_spec, dict):
            raise SimCompareError(f"scenario spec is not a JSON object: {scenario_spec_path}")
        if scenario_spec.get("scenario_id") != scenario_id:
            raise SimCompareError(
                f"scenario_id mismatch: --scenario-id={scenario_id} but scenario-spec has {scenario_spec.get('scenario_id')}"
            )
    else:
        scenario_spec = {
            "scenario_spec_version": "scenario-spec/v1",
            "scenario_id": scenario_id,
            "symbol_set": {
                "mode": "explicit-list",
                "symbols": sorted(symbols),
                "symbol_set_id": "legacy-derived",
            },
            "session_slice": {
                "session_date": session_date,
                "slice_label": "full-session",
                "start_local": "09:00:00",
                "end_local": "13:30:00",
            },
            "event_source": {
                "source_id": market_event_source_id,
                "source_kind": market_event_source_kind,
                "source_ref": market_event_source_ref,
                "time_range_utc": {
                    "start": min_event_time,
                    "end": max_event_time,
                },
                "adjustment_mode": "raw",
            },
            "market_clock": {
                "timezone": "Asia/Taipei",
                "calendar": "TWSE",
            },
            "execution_model": {
                "fee_model": execution_model["fee_model"],
                "tax_model": execution_model["tax_model"],
                "slippage_model": execution_model["slippage_model"],
                "rounding_rule": execution_model["rounding_rule"],
                "fill_model": execution_model["fill_model"],
            },
            "determinism": {
                "mode": "best-effort",
                "random_seed": None,
                "notes": determinism_note,
            },
        }

    session_slice = scenario_spec.get("session_slice") if isinstance(scenario_spec, dict) else None
    if isinstance(session_slice, dict):
        start_local = session_slice.get("start_local")
        end_local = session_slice.get("end_local")
        if (
            isinstance(start_local, str)
            and isinstance(end_local, str)
            and min_event_time is not None
            and max_event_time is not None
        ):
            try:
                session_start_local = datetime.fromisoformat(f"{session_date}T{start_local}").replace(
                    tzinfo=TWSE_TIMEZONE
                )
                session_end_local = datetime.fromisoformat(f"{session_date}T{end_local}").replace(
                    tzinfo=TWSE_TIMEZONE
                )
            except ValueError:
                session_start_local = None
                session_end_local = None
            observed_start = parse_utc_timestamp(min_event_time)
            observed_end = parse_utc_timestamp(max_event_time)
            if (
                session_start_local is not None
                and session_end_local is not None
                and observed_start is not None
                and observed_end is not None
            ):
                observed_start_local = observed_start.astimezone(TWSE_TIMEZONE)
                observed_end_local = observed_end.astimezone(TWSE_TIMEZONE)
                if observed_start_local > session_start_local or observed_end_local < session_end_local:
                    add_anomaly(
                        "major",
                        "session-coverage-partial",
                        (
                            "Observed source coverage does not span the declared session slice "
                            f"({observed_start_local.strftime('%H:%M:%S')} -> "
                            f"{observed_end_local.strftime('%H:%M:%S')} vs declared "
                            f"{start_local} -> {end_local})."
                        ),
                    )

    scenario_fingerprint = sha256_hex(canonical_json_bytes(scenario_spec))
    scenario_spec_path_out = output_dir / "scenario-spec.json"
    _write_json(scenario_spec_path_out, scenario_spec)

    pnl_summary = {
        "currency": "TWD",
        "realized_pnl_gross": 0.0,
        "fees_total": 0.0,
        "taxes_total": 0.0,
        "realized_pnl_net": 0.0,
        # NOTE: This normalizer does not currently emit fills/positions/PnL; keep
        # pnl-summary aligned with that truth. Any legacy "entry" metrics are
        # carried as diagnostic fields instead of being reported as executed entries.
        "entry_count": 0,
        "exit_count": 0,
        "exit_reason_counts": {},
        "win_count": 0,
        "loss_count": 0,
        "max_position_qty": 0.0,
        "entry_request_count": execution_total,
    }

    gate_reasons = _parse_json(baseline_dir / "gate_reasons.json", default={})
    if isinstance(gate_reasons, dict):
        counts = gate_reasons.get("counts")
        if isinstance(counts, dict):
            maybe_entries = counts.get("entries_total")
            if isinstance(maybe_entries, (int, float)):
                pnl_summary["entry_signal_count"] = int(maybe_entries)

    _write_json(output_dir / "pnl-summary.json", pnl_summary)

    actor_key = config_snapshot_actor_key.strip()
    if not actor_key:
        raise SimCompareError("config_snapshot_actor_key must be non-empty")

    config_snapshot = {
        "scenario_id": scenario_id,
        "deck_id": "legacy-baseline-deck",
        "deck_version": "legacy/v0",
        "cards": [{"card_id": "legacy-baseline-card", "card_version": "legacy/v0"}],
        "global_config_version": "legacy/v0",
        "config_hash": _hash_text(f"{baseline_dir}:{session_date}"),
        actor_key: {
            "name": emitter_name,
            "version": emitter_version,
            "source_dir": str(baseline_dir),
            "event_sources": [str(path) for path in event_sources],
        },
    }
    _write_json(output_dir / "config-snapshot.json", config_snapshot)

    _write_json(output_dir / "anomalies.json", {"anomalies": anomalies})

    artifact_files = [
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
        "file-index.json",
    ]

    run_manifest = {
        "schema_version": "sim-artifacts/v1",
        "run_id": run_id,
        "lane": lane,
        "run_type": run_type,
        "scenario_id": scenario_id,
        "scenario_spec_version": scenario_spec.get("scenario_spec_version"),
        "scenario_fingerprint": scenario_fingerprint,
        "session_date": session_date,
        "started_at_utc": min_event_time or started_at_utc,
        "ended_at_utc": max_event_time or now_utc_iso(),
        "status": "partial" if anomalies else "success",
        "provenance": {
            "engine_name": engine_name,
            "engine_git_sha": "unknown",
            "dependency_lock_hash": "unknown",
            "config_hash": config_snapshot["config_hash"],
            "python_version": sys.version.split()[0],
        },
        "market_event_source": {
            "source_id": market_event_source_id,
            "source_kind": market_event_source_kind,
            "source_ref": market_event_source_ref,
            "timezone": "Asia/Taipei",
            "calendar": "TWSE",
            "time_range": {
                "start": min_event_time,
                "end": max_event_time,
            },
            "adjustment_mode": "raw",
        },
        "session_phase_contract": session_phase_contract,
        "session_phase_trace": [entry.as_dict() for entry in session_phase_trace],
        "open_discovery_summary": open_discovery_summary,
        "execution_model": execution_model,
        "capability_posture": {
            "market_data_enabled": True,
            "trade_enabled": False,
            "account_query_enabled": False,
        },
        "artifact_files": artifact_files,
    }
    _write_json(output_dir / "run-manifest.json", run_manifest)

    file_entries: list[dict[str, Any]] = []
    for relative_name in artifact_files:
        if relative_name == "file-index.json":
            continue
        path = output_dir / relative_name
        if not path.exists():
            continue
        file_entries.append(
            {
                "path": relative_name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    file_index = {
        "schema_version": "sim-artifacts/v1",
        "run_id": run_id,
        "generated_at_utc": now_utc_iso(),
        "files": file_entries,
        "notes": [
            "file-index.json self-hash is intentionally omitted to avoid recursive checksum instability"
        ],
    }
    _write_json(output_dir / "file-index.json", file_index)

    summary = {
        "bundle_dir": str(output_dir),
        "run_id": run_id,
        "scenario_id": scenario_id,
        "scenario_fingerprint": scenario_fingerprint,
        "lane": lane,
        "counts": {
            "events": event_total,
            "decisions": decisions_total,
            "features": feature_total,
            "intents": intent_total,
            "risk_receipts": risk_total,
            "execution_requests": execution_total,
            "order_lifecycle": order_lifecycle_total,
            "fills": 0,
            "positions": 0,
            "anomalies": len(anomalies),
        },
    }
    return summary


def _read_run_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "run-manifest.json"
    if not manifest_path.exists():
        raise SimCompareError(f"missing run-manifest.json in {bundle_dir}")
    payload = _parse_json(manifest_path)
    if not isinstance(payload, dict):
        raise SimCompareError(f"run-manifest.json is not a JSON object in {bundle_dir}")
    return payload


def resolve_bundle_dir(path: Path) -> Path:
    resolved = path.resolve()
    if resolved.is_dir():
        return resolved
    if resolved.is_file() and resolved.name == "run-manifest.json":
        return resolved.parent
    raise SimCompareError(f"bundle path must be a directory or run-manifest.json: {path}")


def validate_bundle(bundle_dir: Path) -> BundleValidationResult:
    bundle_dir = resolve_bundle_dir(bundle_dir)
    manifest = _read_run_manifest(bundle_dir)
    errors: list[str] = []
    warnings: list[str] = []

    for name in BUNDLE_REQUIRED_FILES:
        if not (bundle_dir / name).exists():
            errors.append(f"missing required artifact: {name}")

    file_index = _parse_json(bundle_dir / "file-index.json", default={})
    entries: dict[str, dict[str, Any]] = {}
    if isinstance(file_index, dict):
        raw_files = file_index.get("files")
        if isinstance(raw_files, list):
            for item in raw_files:
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    entries[item["path"]] = item

    for name in BUNDLE_REQUIRED_FILES:
        if name == "file-index.json":
            continue
        artifact_path = bundle_dir / name
        if not artifact_path.exists():
            continue

        if name not in entries:
            errors.append(f"file-index missing entry for {name}")
            continue

        expected_sha = entries[name].get("sha256")
        if not isinstance(expected_sha, str) or not expected_sha:
            errors.append(f"file-index entry missing sha256 for {name}")
            continue

        actual_sha = sha256_file(artifact_path)
        if actual_sha != expected_sha:
            errors.append(f"checksum mismatch for {name}")

    counts = {
        "fills": _line_count(bundle_dir / "fills.jsonl") if (bundle_dir / "fills.jsonl").exists() else 0,
        "orders": (
            _line_count(bundle_dir / "order-lifecycle.jsonl")
            if (bundle_dir / "order-lifecycle.jsonl").exists()
            else 0
        ),
        "intents": (
            _line_count(bundle_dir / "intent-log.jsonl")
            if (bundle_dir / "intent-log.jsonl").exists()
            else 0
        ),
        "risk": (
            _line_count(bundle_dir / "risk-receipts.jsonl")
            if (bundle_dir / "risk-receipts.jsonl").exists()
            else 0
        ),
    }

    anomalies_by_severity: dict[str, int] = {"critical": 0, "major": 0, "minor": 0, "info": 0}
    anomalies_payload = _parse_json(bundle_dir / "anomalies.json", default={})
    if isinstance(anomalies_payload, dict):
        anomalies = anomalies_payload.get("anomalies")
        if isinstance(anomalies, list):
            for anomaly in anomalies:
                if not isinstance(anomaly, dict):
                    continue
                severity = anomaly.get("severity")
                if isinstance(severity, str) and severity in anomalies_by_severity:
                    anomalies_by_severity[severity] += 1

    execution_model = manifest.get("execution_model")
    if not isinstance(execution_model, dict):
        errors.append("run-manifest execution_model is missing or not an object")
        execution_model = {}
    execution_model_hash = sha256_hex(canonical_json_bytes(execution_model))

    fill_model = execution_model.get("fill_model")
    if fill_model not in ALLOWED_SIM_FILL_MODELS:
        errors.append(
            "execution_model.fill_model must be one of "
            f"{sorted(ALLOWED_SIM_FILL_MODELS)} for M1 sim-only runs"
        )

    capability_posture = manifest.get("capability_posture")
    if isinstance(capability_posture, dict):
        if capability_posture.get("trade_enabled") is True:
            errors.append("capability_posture.trade_enabled must remain false for M1")
    else:
        warnings.append("capability_posture missing in run-manifest")

    phase_contract = manifest.get("session_phase_contract")
    if not isinstance(phase_contract, dict):
        errors.append("run-manifest session_phase_contract is missing or not an object")
    else:
        version = phase_contract.get("version")
        if not isinstance(version, str) or not version.startswith("twse-session-phase/"):
            errors.append("run-manifest session_phase_contract.version is missing or invalid")

    phase_trace = manifest.get("session_phase_trace")
    if not isinstance(phase_trace, list) or not phase_trace:
        errors.append("run-manifest session_phase_trace is missing or empty")

    return BundleValidationResult(
        bundle_dir=bundle_dir,
        manifest=manifest,
        errors=errors,
        warnings=warnings,
        counts=counts,
        anomalies_by_severity=anomalies_by_severity,
        execution_model_hash=execution_model_hash,
    )


def compare_bundles(
    *,
    baseline: Path,
    candidate: Path,
    output_dir: Path,
    require_scenario_fingerprint: bool = True,
) -> dict[str, Any]:
    baseline_result = validate_bundle(baseline)
    candidate_result = validate_bundle(candidate)

    hard_fail_reasons: list[str] = []

    for error in baseline_result.errors:
        hard_fail_reasons.append(f"baseline: {error}")
    for error in candidate_result.errors:
        hard_fail_reasons.append(f"candidate: {error}")

    baseline_manifest = baseline_result.manifest
    candidate_manifest = candidate_result.manifest

    baseline_scenario = baseline_manifest.get("scenario_id")
    candidate_scenario = candidate_manifest.get("scenario_id")
    if baseline_scenario != candidate_scenario:
        hard_fail_reasons.append(
            f"scenario_id mismatch: baseline={baseline_scenario} candidate={candidate_scenario}"
        )

    baseline_fp = baseline_manifest.get("scenario_fingerprint")
    candidate_fp = candidate_manifest.get("scenario_fingerprint")
    if require_scenario_fingerprint:
        if not isinstance(baseline_fp, str) or not isinstance(candidate_fp, str):
            hard_fail_reasons.append(
                "scenario_fingerprint missing in one or both run manifests (M1 evidence requires it)"
            )
        elif baseline_fp != candidate_fp:
            hard_fail_reasons.append(
                f"scenario_fingerprint mismatch: baseline={baseline_fp} candidate={candidate_fp}"
            )

    if baseline_result.execution_model_hash != candidate_result.execution_model_hash:
        hard_fail_reasons.append(
            "execution_model mismatch (hard stop): canonical execution_model hash differs"
        )

    status = "fail" if hard_fail_reasons else "pass"

    baseline_pnl = _parse_json(baseline_result.bundle_dir / "pnl-summary.json", default={})
    candidate_pnl = _parse_json(candidate_result.bundle_dir / "pnl-summary.json", default={})

    diff_payload = {
        "compare_version": "m2-decision-grade/v0",
        "status": status,
        "counts": {
            "fills": {
                "baseline": baseline_result.counts["fills"],
                "candidate": candidate_result.counts["fills"],
            },
            "orders": {
                "baseline": baseline_result.counts["orders"],
                "candidate": candidate_result.counts["orders"],
            },
            "intents": {
                "baseline": baseline_result.counts["intents"],
                "candidate": candidate_result.counts["intents"],
            },
            "risk_decisions": {
                "baseline": baseline_result.counts["risk"],
                "candidate": candidate_result.counts["risk"],
            },
        },
        "pnl_reported": {
            "baseline": {
                "realized_pnl_gross": baseline_pnl.get("realized_pnl_gross"),
                "realized_pnl_net": baseline_pnl.get("realized_pnl_net"),
            },
            "candidate": {
                "realized_pnl_gross": candidate_pnl.get("realized_pnl_gross"),
                "realized_pnl_net": candidate_pnl.get("realized_pnl_net"),
            },
        },
        "anomalies": {
            "baseline": baseline_result.anomalies_by_severity,
            "candidate": candidate_result.anomalies_by_severity,
        },
        "decision_grade_diff": {
            "per_symbol_totals": {
                "baseline": baseline_pnl.get("per_symbol_totals", {}),
                "candidate": candidate_pnl.get("per_symbol_totals", {}),
            },
            "exposure": {
                "baseline": {
                    "max_exposure": baseline_pnl.get("max_exposure", baseline_pnl.get("max_position_qty")),
                    "max_position_qty": baseline_pnl.get("max_position_qty"),
                },
                "candidate": {
                    "max_exposure": candidate_pnl.get("max_exposure", candidate_pnl.get("max_position_qty")),
                    "max_position_qty": candidate_pnl.get("max_position_qty"),
                },
            },
            "exit_reason_distribution": {
                "baseline": baseline_pnl.get("exit_reason_counts", {}),
                "candidate": candidate_pnl.get("exit_reason_counts", {}),
            },
            "realized_totals": {
                "baseline": {
                    "realized_pnl_gross": baseline_pnl.get("realized_pnl_gross"),
                    "fees_total": baseline_pnl.get("fees_total"),
                    "taxes_total": baseline_pnl.get("taxes_total"),
                    "realized_pnl_net": baseline_pnl.get("realized_pnl_net"),
                },
                "candidate": {
                    "realized_pnl_gross": candidate_pnl.get("realized_pnl_gross"),
                    "fees_total": candidate_pnl.get("fees_total"),
                    "taxes_total": candidate_pnl.get("taxes_total"),
                    "realized_pnl_net": candidate_pnl.get("realized_pnl_net"),
                },
            },
        },
    }

    compare_manifest = {
        "compare_version": "m2-decision-grade/v0",
        "status": status,
        "hard_fail_reasons": hard_fail_reasons,
        "baseline": {
            "run_id": baseline_manifest.get("run_id"),
            "lane": baseline_manifest.get("lane"),
            "bundle_dir": str(baseline_result.bundle_dir),
        },
        "candidate": {
            "run_id": candidate_manifest.get("run_id"),
            "lane": candidate_manifest.get("lane"),
            "bundle_dir": str(candidate_result.bundle_dir),
        },
        "scenario": {
            "scenario_id": baseline_scenario,
            "scenario_fingerprint": baseline_fp,
        },
        "execution_model": {
            "baseline": {
                "hash": baseline_result.execution_model_hash,
                "fill_model": (
                    baseline_manifest.get("execution_model") or {}
                ).get("fill_model"),
            },
            "candidate": {
                "hash": candidate_result.execution_model_hash,
                "fill_model": (
                    candidate_manifest.get("execution_model") or {}
                ).get("fill_model"),
            },
        },
    }

    output_dir = output_dir.resolve()
    _ensure_dir(output_dir)
    _write_json(output_dir / "compare-manifest.json", compare_manifest)
    _write_json(output_dir / "diff.json", diff_payload)

    summary_lines = [
        "# Decision-Grade Comparator Summary",
        "",
        f"- status: **{status.upper()}**",
        f"- baseline run: `{baseline_manifest.get('run_id')}` ({baseline_manifest.get('lane')})",
        f"- candidate run: `{candidate_manifest.get('run_id')}` ({candidate_manifest.get('lane')})",
        f"- scenario_id: `{baseline_scenario}`",
        "",
        "## Hard fail reasons",
    ]
    if hard_fail_reasons:
        summary_lines.extend(f"- {reason}" for reason in hard_fail_reasons)
    else:
        summary_lines.append("- (none)")

    summary_lines.extend(
        [
            "",
            "## Counts scaffold",
            f"- fills: baseline={baseline_result.counts['fills']} candidate={candidate_result.counts['fills']}",
            f"- orders: baseline={baseline_result.counts['orders']} candidate={candidate_result.counts['orders']}",
            f"- intents: baseline={baseline_result.counts['intents']} candidate={candidate_result.counts['intents']}",
            f"- risk decisions: baseline={baseline_result.counts['risk']} candidate={candidate_result.counts['risk']}",
            "",
            "## Notes",
            "- Decision-grade diff now includes per-symbol totals, exposure maxima, exit-reason distribution, and realized totals.",
            "- execution_model hash mismatch remains a hard stop.",
        ]
    )

    (output_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    return {
        "status": status,
        "output_dir": str(output_dir),
        "hard_fail_reasons": hard_fail_reasons,
        "compare_manifest": str(output_dir / "compare-manifest.json"),
        "diff": str(output_dir / "diff.json"),
        "summary": str(output_dir / "summary.md"),
    }
