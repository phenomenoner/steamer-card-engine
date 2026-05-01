from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any

from steamer_card_engine.adapters.fixture_exchange import (
    FIXTURE_ADAPTER_ID,
    FixturePaperOnlyAdapter,
    build_fixture_replay_payload,
)
from steamer_card_engine.paper import ledger
from steamer_card_engine.paper.receipts import stable_hash, with_receipt_hash

FIXED_CREATED_AT = "1970-01-01T00:00:00Z"


@dataclass(frozen=True, slots=True)
class PaperRunError(Exception):
    payload: dict[str, Any]
    exit_code: int = 4

    def __str__(self) -> str:
        return str(self.payload.get("stable_reason") or self.payload.get("reason_code") or "paper run failed")


def _risk_profile_hash(*, max_position: int, max_loss_placeholder: int, stale_signal_seconds: int) -> str:
    return stable_hash(
        {
            "max_position": max_position,
            "max_loss_placeholder": max_loss_placeholder,
            "stale_signal_seconds": stale_signal_seconds,
            "duplicate_order_guard": True,
            "stale_signal_guard": True,
        }
    )


def _run_id(adapter_id: str, replay_hash: str, risk_profile_hash: str) -> str:
    return f"paper-run:{stable_hash(adapter_id + replay_hash + ledger.LEDGER_SCHEMA_VERSION + risk_profile_hash)[:16]}"


def _order_id(run_id: str, request_id: str, symbol: str, side: str, quantity: int, order_type: str) -> str:
    return f"paper-order:{stable_hash(run_id + request_id + symbol + side + str(quantity) + order_type)[:16]}"


def _dedupe_key(adapter_id: str, case_id: str | None, request_id: str, symbol: str, side: str, quantity: int, order_type: str) -> str:
    return stable_hash(adapter_id + str(case_id or "") + request_id + symbol + side + str(quantity) + order_type)


def _fill_id(order_id: str, quantity: int, fill_price: float) -> str:
    return f"paper-fill:{stable_hash(order_id + ledger.FILL_MODEL + str(quantity) + str(fill_price))[:16]}"


def _reject_payload(*, adapter_id: str, reason_code: str, stable_reason: str, ledger_path: Path | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "paper-run/v1",
        "ledger_schema_version": ledger.LEDGER_SCHEMA_VERSION,
        "adapter": {"id": adapter_id, "vendor": "fixture", "version": "unknown"},
        "mode": "paper",
        "execution": "local-ledger-only",
        "decision": "fail",
        "reason_code": reason_code,
        "stable_reason": stable_reason,
        "risk": {"decision": "fail", "failures": [{"code": reason_code, "detail": stable_reason}]},
        "summary": {
            "intents_seen": 0,
            "orders_accepted": 0,
            "orders_rejected": 0,
            "fills": 0,
            "cancels": 0,
            "broker_native_order_count": 0,
        },
        "no_network": True,
        "topology_changed": False,
        "live_readiness_claim": False,
    }
    if ledger_path is not None:
        payload["ledger"] = {"path": str(ledger_path), "backend": "sqlite"}
    return payload


def _adapter_public() -> dict[str, str]:
    return FixturePaperOnlyAdapter().identity.to_public_dict()


def _replay(adapter_id: str, fixtures_path: Path) -> dict[str, Any]:
    payload, exit_code = build_fixture_replay_payload(adapter_id=adapter_id, fixtures_path=fixtures_path)
    if exit_code != 0:
        raise PaperRunError(
            _reject_payload(
                adapter_id=adapter_id,
                reason_code=str(payload.get("reason_code") or "adapter_replay_failed"),
                stable_reason=str(payload.get("stable_reason") or "adapter replay failed closed"),
            ),
            exit_code,
        )
    return payload


def _simulation_intents(replay_payload: dict[str, Any]) -> list[dict[str, Any]]:
    intents: list[dict[str, Any]] = []
    decisions = replay_payload.get("decisions")
    if not isinstance(decisions, list):
        return intents
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        signal = decision.get("normalized_signal")
        if isinstance(signal, dict) and signal.get("decision") != "allow":
            continue
        intent = decision.get("simulation_intent")
        native = decision.get("broker_native_orders")
        if isinstance(native, list) and native:
            raise PaperRunError(
                _reject_payload(
                    adapter_id=str((replay_payload.get("adapter") or {}).get("id") if isinstance(replay_payload.get("adapter"), dict) else FIXTURE_ADAPTER_ID),
                    reason_code="broker_native_order_present",
                    stable_reason="broker-native order payloads are not permitted in paper ledger replay",
                )
            )
        if isinstance(intent, dict):
            enriched = dict(intent)
            enriched["case_id"] = decision.get("case_id")
            intents.append(enriched)
    return intents


def _preflight_orders(
    *, adapter_id: str, run_id: str, intents: list[dict[str, Any]], max_position: int, conn: sqlite3.Connection
) -> tuple[list[ledger.PaperOrder], list[ledger.PaperFill], list[dict[str, str]]]:
    failures: list[dict[str, str]] = []
    orders: list[ledger.PaperOrder] = []
    fills: list[ledger.PaperFill] = []
    positions = ledger.current_positions(conn)
    dedupe_keys: list[str] = []
    for intent in intents:
        request_id = str(intent.get("request_id") or "")
        symbol = str(intent.get("symbol") or "")
        side = str(intent.get("side") or "buy")
        quantity = int(intent.get("quantity") or 0)
        order_type = str(intent.get("order_type") or "market")
        case_id = str(intent.get("case_id")) if intent.get("case_id") is not None else None
        key = _dedupe_key(adapter_id, case_id, request_id, symbol, side, quantity, order_type)
        dedupe_keys.append(key)
        if side not in {"buy", "sell"} or quantity <= 0 or not symbol or not request_id:
            failures.append({"code": "invalid_intent", "detail": request_id or case_id or "unknown"})
            continue
        signed = quantity if side == "buy" else -quantity
        resulting_position = positions.get(symbol, 0) + signed
        if abs(resulting_position) > max_position:
            failures.append({"code": "max_position_exceeded", "detail": f"{symbol} resulting_position={resulting_position} max={max_position}"})
            continue
        positions[symbol] = resulting_position
        order_id = _order_id(run_id, request_id, symbol, side, quantity, order_type)
        orders.append(
            ledger.PaperOrder(
                order_id=order_id,
                run_id=run_id,
                request_id=request_id,
                dedupe_key=key,
                case_id=case_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                status="filled",
                reason_code="paper_risk_passed",
                stable_reason="local fixture-only paper risk accepted and filled deterministically",
                created_at=FIXED_CREATED_AT,
                updated_at=FIXED_CREATED_AT,
            )
        )
        fills.append(
            ledger.PaperFill(
                fill_id=_fill_id(order_id, quantity, 1.0),
                order_id=order_id,
                run_id=run_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                fill_price=1.0,
                filled_at=FIXED_CREATED_AT,
            )
        )
    existing = ledger.dedupe_keys_present(conn, dedupe_keys)
    if existing:
        failures.insert(0, {"code": "duplicate_order", "detail": f"{len(existing)} duplicate dedupe key(s) already in ledger"})
    return orders, fills, failures


def _base_receipt(
    *,
    replay_payload: dict[str, Any],
    ledger_path: Path,
    run_id: str,
    risk_profile_hash: str,
    max_position: int,
    max_loss_placeholder: int,
    stale_signal_seconds: int,
    risk_failures: list[dict[str, str]],
    intents_seen: int,
    orders_accepted: int,
    fills: int,
) -> dict[str, Any]:
    hashes = replay_payload.get("hashes") if isinstance(replay_payload.get("hashes"), dict) else {}
    return {
        "schema_version": "paper-run/v1",
        "ledger_schema_version": ledger.LEDGER_SCHEMA_VERSION,
        "adapter": _adapter_public(),
        "mode": "paper",
        "execution": "local-ledger-only",
        "ledger": {"path": str(ledger_path), "backend": "sqlite"},
        "hashes": {
            "run_id": run_id,
            "replay_hash": str(hashes.get("replay_hash") or ""),
            "fixture_hash": str(hashes.get("fixture_hash") or ""),
            "adapter_hash": str(hashes.get("adapter_hash") or ""),
            "input_hash": str(hashes.get("input_hash") or ""),
            "risk_profile_hash": risk_profile_hash,
            "receipt_hash": "",
        },
        "risk": {
            "decision": "fail" if risk_failures else "pass",
            "max_position": max_position,
            "max_loss_placeholder": max_loss_placeholder,
            "max_loss_model": "placeholder-only; no market-real PnL claim",
            "stale_signal_seconds": stale_signal_seconds,
            "duplicate_order_guard": True,
            "stale_signal_guard": True,
            "stale_signal_evidence": "fixture logical replay only; not evidence of market freshness",
            "failures": risk_failures,
        },
        "summary": {
            "intents_seen": intents_seen,
            "orders_accepted": orders_accepted,
            "orders_rejected": len(risk_failures),
            "fills": fills,
            "cancels": 0,
            "broker_native_order_count": int((replay_payload.get("summary") or {}).get("broker_native_order_count", 0))
            if isinstance(replay_payload.get("summary"), dict)
            else 0,
        },
        "no_network": True,
        "topology_changed": False,
        "live_readiness_claim": False,
    }


def run_paper_replay(
    *,
    adapter_id: str,
    fixtures_path: Path,
    ledger_path: Path,
    receipt_path: Path | None,
    max_position: int,
    max_loss_placeholder: int,
    stale_signal_seconds: int,
) -> tuple[dict[str, Any], int]:
    if adapter_id != FIXTURE_ADAPTER_ID:
        raise PaperRunError(
            _reject_payload(
                adapter_id=adapter_id,
                reason_code="unknown_adapter",
                stable_reason="unknown adapter is not permitted for local paper ledger replay",
                ledger_path=ledger_path,
            )
        )
    replay_payload = _replay(adapter_id, fixtures_path)
    intents = _simulation_intents(replay_payload)
    hashes = replay_payload.get("hashes") if isinstance(replay_payload.get("hashes"), dict) else {}
    risk_hash = _risk_profile_hash(
        max_position=max_position,
        max_loss_placeholder=max_loss_placeholder,
        stale_signal_seconds=stale_signal_seconds,
    )
    run_id = _run_id(adapter_id, str(hashes.get("replay_hash") or ""), risk_hash)

    conn = ledger.connect(ledger_path)
    try:
        ledger.initialize(conn)
        conn.commit()
        conn.execute("BEGIN")
        orders, fills, failures = _preflight_orders(
            adapter_id=adapter_id,
            run_id=run_id,
            intents=intents,
            max_position=max_position,
            conn=conn,
        )
        if int((replay_payload.get("summary") or {}).get("broker_native_order_count", 0)) if isinstance(replay_payload.get("summary"), dict) else 0:
            failures.append({"code": "broker_native_order_present", "detail": "broker-native order count must be zero"})
        if failures:
            conn.rollback()
            receipt = with_receipt_hash(
                _base_receipt(
                    replay_payload=replay_payload,
                    ledger_path=ledger_path,
                    run_id=run_id,
                    risk_profile_hash=risk_hash,
                    max_position=max_position,
                    max_loss_placeholder=max_loss_placeholder,
                    stale_signal_seconds=stale_signal_seconds,
                    risk_failures=failures,
                    intents_seen=len(intents),
                    orders_accepted=0,
                    fills=0,
                )
            )
            if receipt_path:
                receipt_path.parent.mkdir(parents=True, exist_ok=True)
                receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return receipt, 4

        receipt = with_receipt_hash(
            _base_receipt(
                replay_payload=replay_payload,
                ledger_path=ledger_path,
                run_id=run_id,
                risk_profile_hash=risk_hash,
                max_position=max_position,
                max_loss_placeholder=max_loss_placeholder,
                stale_signal_seconds=stale_signal_seconds,
                risk_failures=[],
                intents_seen=len(intents),
                orders_accepted=len(orders),
                fills=len(fills),
            )
        )
        ledger.insert_run(
            conn,
            run_id=run_id,
            created_at=FIXED_CREATED_AT,
            adapter_id=adapter_id,
            fixture_hash=str(hashes.get("fixture_hash") or ""),
            adapter_hash=str(hashes.get("adapter_hash") or ""),
            replay_hash=str(hashes.get("replay_hash") or ""),
            input_hash=str(hashes.get("input_hash") or ""),
            risk_profile_hash=risk_hash,
            receipt_hash=str(receipt["hashes"]["receipt_hash"]),
            status="filled",
        )
        seq = 0
        for order, fill in zip(orders, fills, strict=True):
            ledger.insert_event(conn, run_id=run_id, order_id=order.order_id, event_type="intent_seen", event_seq=seq, payload={"request_id": order.request_id, "case_id": order.case_id}, created_at=FIXED_CREATED_AT)
            seq += 1
            ledger.insert_order(conn, order)
            ledger.insert_event(conn, run_id=run_id, order_id=order.order_id, event_type="order_accepted", event_seq=seq, payload={"order_id": order.order_id}, created_at=FIXED_CREATED_AT)
            seq += 1
            ledger.insert_fill(conn, fill)
            ledger.insert_event(conn, run_id=run_id, order_id=order.order_id, event_type="order_filled", event_seq=seq, payload={"fill_id": fill.fill_id, "fill_model": fill.fill_model}, created_at=FIXED_CREATED_AT)
            seq += 1
        conn.commit()
        if receipt_path:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt, 0
    except sqlite3.IntegrityError as error:
        conn.rollback()
        receipt = with_receipt_hash(
            _base_receipt(
                replay_payload=replay_payload,
                ledger_path=ledger_path,
                run_id=run_id,
                risk_profile_hash=risk_hash,
                max_position=max_position,
                max_loss_placeholder=max_loss_placeholder,
                stale_signal_seconds=stale_signal_seconds,
                risk_failures=[{"code": "ledger_integrity_error", "detail": str(error)}],
                intents_seen=len(intents),
                orders_accepted=0,
                fills=0,
            )
        )
        if receipt_path:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt, 4
    finally:
        conn.close()


def audit_paper_ledger(*, ledger_path: Path) -> tuple[dict[str, Any], int]:
    if not ledger_path.exists():
        payload = {
            "schema_version": "paper-audit/v1",
            "ledger_schema_version": ledger.LEDGER_SCHEMA_VERSION,
            "decision": "fail",
            "counts": {"orders": 0, "accepted": 0, "rejected": 0, "fills": 0, "cancels": 0, "events": 0},
            "account_summary": {"positions": [], "realized_pnl": 0.0, "pnl_model": ledger.PNL_MODEL},
            "invariant_failures": [{"code": "ledger_missing", "detail": str(ledger_path)}],
            "no_network": True,
            "topology_changed": False,
        }
        return payload, 4
    conn = ledger.connect(ledger_path)
    try:
        payload = ledger.audit(conn)
        return payload, 0 if payload["decision"] == "pass" else 4
    finally:
        conn.close()
