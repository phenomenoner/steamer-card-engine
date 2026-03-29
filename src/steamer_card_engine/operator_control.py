from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from steamer_card_engine.manifest import load_auth_profile, load_deck_manifest


OPERATOR_REFUSED_EXIT = 4
OPERATOR_CONFIRMATION_REQUIRED_EXIT = 5

MIN_ARM_TTL_SECONDS = 30
MAX_ARM_TTL_SECONDS = 8 * 60 * 60


@dataclass(slots=True)
class OperatorResult:
    payload: dict[str, Any]
    exit_code: int


def _iso_utc(ts: datetime) -> str:
    return ts.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": "operator-posture/v1",
        "mode": "live",
        "session": {
            "session_id": "seed-session",
            "account_no": "unknown-account",
            "auth_mode": "unknown",
        },
        "capabilities": {
            "marketdata_enabled": False,
            "account_query_enabled": False,
            "trade_enabled": False,
        },
        "health_status": {
            "runtime": "seed-ok",
            "session": "unknown",
        },
        "armed_live": False,
        "armed_scope": None,
        "recent_actions": [],
    }


def _ensure_state_shape(state: dict[str, Any]) -> dict[str, Any]:
    baseline = _default_state()

    for key, value in baseline.items():
        state.setdefault(key, value)

    if not isinstance(state["session"], dict):
        state["session"] = baseline["session"].copy()
    if not isinstance(state["capabilities"], dict):
        state["capabilities"] = baseline["capabilities"].copy()
    if not isinstance(state["health_status"], dict):
        state["health_status"] = baseline["health_status"].copy()
    if not isinstance(state.get("recent_actions"), list):
        state["recent_actions"] = []

    for key, value in baseline["session"].items():
        state["session"].setdefault(key, value)
    for key, value in baseline["capabilities"].items():
        state["capabilities"].setdefault(key, value)
    for key, value in baseline["health_status"].items():
        state["health_status"].setdefault(key, value)

    state["armed_live"] = bool(state.get("armed_live"))
    if not state["armed_live"]:
        state["armed_scope"] = None

    return state


def load_operator_state(state_file: Path) -> dict[str, Any]:
    if not state_file.exists():
        return _default_state()

    payload = json.loads(state_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"operator state file must contain a JSON object: {state_file}")
    return _ensure_state_shape(payload)


def save_operator_state(state_file: Path, state: dict[str, Any]) -> None:
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_recent_action(state: dict[str, Any], receipt: dict[str, Any]) -> None:
    entry = {
        "receipt_id": receipt["receipt_id"],
        "action": receipt["action"],
        "status": receipt["status"],
        "acted_at": receipt["acted_at"],
    }
    state["recent_actions"].append(entry)
    state["recent_actions"] = state["recent_actions"][-20:]


def _resolve_operator_id(operator_id: str | None) -> str:
    if operator_id:
        return operator_id
    return os.environ.get("USER", "unknown-operator")


def _evaluate_arm_window(state: dict[str, Any]) -> dict[str, Any]:
    if not state["armed_live"]:
        return {
            "status": "disarmed",
            "allowed": False,
            "reason": "disarmed-posture",
            "details": {"reason": "armed_live=false"},
        }

    armed_scope = state.get("armed_scope")
    if not isinstance(armed_scope, dict):
        return {
            "status": "invalid",
            "allowed": False,
            "reason": "invalid-armed-scope",
            "details": {"reason": "armed_scope_missing_or_non_object"},
        }

    expires_at_raw = armed_scope.get("expires_at")
    if not isinstance(expires_at_raw, str):
        return {
            "status": "invalid",
            "allowed": False,
            "reason": "invalid-armed-scope",
            "details": {"reason": "missing-expires-at"},
        }

    try:
        expires_at = _parse_utc(expires_at_raw)
    except ValueError:
        return {
            "status": "invalid",
            "allowed": False,
            "reason": "invalid-armed-scope",
            "details": {
                "reason": "invalid-expires-at",
                "expires_at": expires_at_raw,
            },
        }

    now = _utc_now()
    if now >= expires_at:
        return {
            "status": "expired",
            "allowed": False,
            "reason": "ttl-expired",
            "details": {
                "reason": "ttl-expired",
                "expired_at": expires_at_raw,
            },
        }

    return {
        "status": "active",
        "allowed": True,
        "reason": "armed-live",
        "details": {
            "expires_at": expires_at_raw,
            "remaining_seconds": int((expires_at - now).total_seconds()),
        },
    }


def _submission_gate(state: dict[str, Any]) -> dict[str, Any]:
    window = _evaluate_arm_window(state)
    return {
        "allowed": bool(window["allowed"]),
        "reason": str(window["reason"]),
    }


def _write_receipt(
    *,
    receipt_dir: Path,
    action: str,
    status: str,
    operator_id: str,
    operator_note: str | None,
    state_file: Path,
    details: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    now = _utc_now()
    receipt_id = f"op-{uuid4().hex}"
    payload = {
        "receipt_id": receipt_id,
        "schema_version": "operator-action-receipt/v1",
        "acted_at": _iso_utc(now),
        "action": action,
        "status": status,
        "operator_id": operator_id,
        "operator_note": operator_note,
        "state_file": str(state_file),
        "details": details,
        "posture": {
            "armed_live": state["armed_live"],
            "armed_scope": state["armed_scope"],
            "order_submission_gate": _submission_gate(state),
        },
    }

    receipt_dir.mkdir(parents=True, exist_ok=True)
    receipt_name = f"{now.strftime('%Y%m%dT%H%M%SZ')}_{action}_{receipt_id[:14]}.json"
    receipt_path = receipt_dir / receipt_name
    receipt_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    payload["receipt_path"] = str(receipt_path)
    return payload


def _apply_auth_profile(
    state: dict[str, Any],
    *,
    auth_profile_path: str | None,
    session_id: str | None,
) -> None:
    if auth_profile_path:
        profile = load_auth_profile(auth_profile_path)
        state["session"]["account_no"] = profile.account
        state["session"]["auth_mode"] = profile.mode
        state["capabilities"] = {
            "marketdata_enabled": profile.marketdata_enabled,
            "account_query_enabled": profile.account_query_enabled,
            "trade_enabled": profile.trade_enabled,
        }
        state["health_status"]["session"] = "ok"

    if session_id:
        state["session"]["session_id"] = session_id


def _resolve_deck(deck_ref: str) -> tuple[str, str]:
    candidates = [Path(deck_ref)]
    if not deck_ref.endswith(".toml"):
        candidates.append(Path("examples/decks") / f"{deck_ref}.toml")
    candidates.append(Path("examples/decks") / deck_ref)

    for candidate in candidates:
        if candidate.exists():
            manifest = load_deck_manifest(str(candidate))
            return manifest.deck_id, str(candidate.resolve())

    raise FileNotFoundError(
        "operator arm-live refused: deck does not resolve to a concrete manifest path "
        f"({deck_ref})"
    )


def _maybe_auto_disarm(
    *,
    state: dict[str, Any],
    state_file: Path,
    receipt_dir: Path,
) -> dict[str, Any] | None:
    window = _evaluate_arm_window(state)
    if window["status"] in {"disarmed", "active"}:
        return None

    previous_scope = state.get("armed_scope")
    state["armed_live"] = False
    state["armed_scope"] = None

    if window["status"] == "expired":
        status = "ttl-expired"
        operator_note = "arm TTL expired"
    else:
        status = "scope-invalid"
        operator_note = "arm scope invalid; auto-disarmed"

    details = {
        "reason": window["details"]["reason"],
        "previous_scope": previous_scope,
    }
    for key, value in window["details"].items():
        if key == "reason":
            continue
        details[key] = value

    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="auto-disarm",
        status=status,
        operator_id="system",
        operator_note=operator_note,
        state_file=state_file,
        details=details,
        state=state,
    )
    _append_recent_action(state, receipt)
    return receipt


def operator_status(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str | None,
    session_id: str | None,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=session_id)

    auto_disarm_receipt = _maybe_auto_disarm(state=state, state_file=state_file, receipt_dir=receipt_dir)

    save_operator_state(state_file, state)

    payload = {
        "mode": state["mode"],
        "session": state["session"],
        "capabilities": state["capabilities"],
        "health_status": state["health_status"],
        "armed_live": state["armed_live"],
        "armed_scope": state["armed_scope"],
        "order_submission_gate": _submission_gate(state),
        "recent_actions": state["recent_actions"][-5:],
        "policy": {
            "arm_ttl_seconds": {
                "min": MIN_ARM_TTL_SECONDS,
                "max": MAX_ARM_TTL_SECONDS,
            }
        },
    }
    if auto_disarm_receipt:
        payload["auto_disarm_receipt"] = auto_disarm_receipt["receipt_path"]

    return OperatorResult(payload=payload, exit_code=0)


def operator_arm_live(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str,
    session_id: str | None,
    deck_ref: str,
    ttl_seconds: int,
    operator_id: str | None,
    operator_note: str | None,
    confirm_live: bool,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=session_id)
    _maybe_auto_disarm(state=state, state_file=state_file, receipt_dir=receipt_dir)

    resolved_operator = _resolve_operator_id(operator_id)

    if not confirm_live:
        receipt = _write_receipt(
            receipt_dir=receipt_dir,
            action="arm-live",
            status="refused-confirmation-required",
            operator_id=resolved_operator,
            operator_note=operator_note,
            state_file=state_file,
            details={"reason": "missing --confirm-live"},
            state=state,
        )
        _append_recent_action(state, receipt)
        save_operator_state(state_file, state)
        return OperatorResult(
            payload={
                "ok": False,
                "error": "operator arm-live refused: missing --confirm-live",
                "receipt_path": receipt["receipt_path"],
            },
            exit_code=OPERATOR_CONFIRMATION_REQUIRED_EXIT,
        )

    if not state["capabilities"]["trade_enabled"]:
        receipt = _write_receipt(
            receipt_dir=receipt_dir,
            action="arm-live",
            status="refused-capability-mismatch",
            operator_id=resolved_operator,
            operator_note=operator_note,
            state_file=state_file,
            details={
                "reason": "trade_enabled=false",
                "capabilities": state["capabilities"],
            },
            state=state,
        )
        _append_recent_action(state, receipt)
        save_operator_state(state_file, state)
        return OperatorResult(
            payload={
                "ok": False,
                "error": "operator arm-live refused: auth capability trade_enabled=false",
                "receipt_path": receipt["receipt_path"],
            },
            exit_code=OPERATOR_REFUSED_EXIT,
        )

    if ttl_seconds < MIN_ARM_TTL_SECONDS or ttl_seconds > MAX_ARM_TTL_SECONDS:
        receipt = _write_receipt(
            receipt_dir=receipt_dir,
            action="arm-live",
            status="refused-ttl-out-of-policy",
            operator_id=resolved_operator,
            operator_note=operator_note,
            state_file=state_file,
            details={
                "reason": "ttl out of policy",
                "ttl_seconds": ttl_seconds,
                "ttl_policy": {
                    "min": MIN_ARM_TTL_SECONDS,
                    "max": MAX_ARM_TTL_SECONDS,
                },
            },
            state=state,
        )
        _append_recent_action(state, receipt)
        save_operator_state(state_file, state)
        return OperatorResult(
            payload={
                "ok": False,
                "error": (
                    "operator arm-live refused: ttl-seconds must be within policy bounds "
                    f"[{MIN_ARM_TTL_SECONDS}, {MAX_ARM_TTL_SECONDS}]"
                ),
                "receipt_path": receipt["receipt_path"],
            },
            exit_code=OPERATOR_REFUSED_EXIT,
        )

    try:
        deck_id, deck_path = _resolve_deck(deck_ref)
    except FileNotFoundError as error:
        receipt = _write_receipt(
            receipt_dir=receipt_dir,
            action="arm-live",
            status="refused-deck-unresolved",
            operator_id=resolved_operator,
            operator_note=operator_note,
            state_file=state_file,
            details={"reason": str(error), "deck_ref": deck_ref},
            state=state,
        )
        _append_recent_action(state, receipt)
        save_operator_state(state_file, state)
        return OperatorResult(
            payload={
                "ok": False,
                "error": str(error),
                "receipt_path": receipt["receipt_path"],
            },
            exit_code=OPERATOR_REFUSED_EXIT,
        )

    armed_at = _utc_now()
    expires_at = armed_at + timedelta(seconds=ttl_seconds)
    state["armed_live"] = True
    state["armed_scope"] = {
        "deck_id": deck_id,
        "deck_ref": deck_path,
        "account_no": state["session"]["account_no"],
        "armed_at": _iso_utc(armed_at),
        "expires_at": _iso_utc(expires_at),
        "ttl_seconds": ttl_seconds,
        "operator_note": operator_note,
    }

    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="arm-live",
        status="armed",
        operator_id=resolved_operator,
        operator_note=operator_note,
        state_file=state_file,
        details={
            "deck_id": deck_id,
            "deck_ref": deck_path,
            "ttl_seconds": ttl_seconds,
        },
        state=state,
    )
    _append_recent_action(state, receipt)
    save_operator_state(state_file, state)

    return OperatorResult(
        payload={
            "ok": True,
            "armed_live": True,
            "armed_scope": state["armed_scope"],
            "receipt_path": receipt["receipt_path"],
        },
        exit_code=0,
    )


def operator_disarm_live(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str | None,
    session_id: str | None,
    operator_id: str | None,
    operator_note: str | None,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=session_id)
    _maybe_auto_disarm(state=state, state_file=state_file, receipt_dir=receipt_dir)

    resolved_operator = _resolve_operator_id(operator_id)
    was_armed = state["armed_live"]
    previous_scope = state["armed_scope"]

    state["armed_live"] = False
    state["armed_scope"] = None

    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="disarm-live",
        status="disarmed",
        operator_id=resolved_operator,
        operator_note=operator_note,
        state_file=state_file,
        details={
            "was_armed": was_armed,
            "previous_scope": previous_scope,
            "in_flight_orders": "unknown(seed-runtime)",
        },
        state=state,
    )
    _append_recent_action(state, receipt)
    save_operator_state(state_file, state)

    return OperatorResult(
        payload={
            "ok": True,
            "armed_live": False,
            "was_armed": was_armed,
            "receipt_path": receipt["receipt_path"],
        },
        exit_code=0,
    )


def operator_flatten(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str | None,
    session_id: str | None,
    mode: str,
    operator_id: str | None,
    operator_note: str | None,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=session_id)
    _maybe_auto_disarm(state=state, state_file=state_file, receipt_dir=receipt_dir)

    resolved_operator = _resolve_operator_id(operator_id)
    was_armed = state["armed_live"]

    state["armed_live"] = False
    state["armed_scope"] = None

    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="flatten",
        status="flatten-issued",
        operator_id=resolved_operator,
        operator_note=operator_note,
        state_file=state_file,
        details={
            "mode": mode,
            "implicit_disarm": was_armed,
            "exit_action_plan": "seed-runtime: flatten request captured as receipt only",
        },
        state=state,
    )
    _append_recent_action(state, receipt)
    save_operator_state(state_file, state)

    return OperatorResult(
        payload={
            "ok": True,
            "flatten_mode": mode,
            "implicit_disarm": was_armed,
            "armed_live": False,
            "receipt_path": receipt["receipt_path"],
        },
        exit_code=0,
    )


def operator_submit_order_smoke(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str | None,
    session_id: str | None,
    symbol: str,
    side: str,
    quantity: int,
    operator_id: str | None,
    operator_note: str | None,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=session_id)
    auto_disarm_receipt = _maybe_auto_disarm(
        state=state,
        state_file=state_file,
        receipt_dir=receipt_dir,
    )

    resolved_operator = _resolve_operator_id(operator_id)
    request = {
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
    }
    submission_gate = _submission_gate(state)

    if not submission_gate["allowed"]:
        details: dict[str, Any] = {
            "reason": "submission gate denied",
            "gate_reason": submission_gate["reason"],
            "request": request,
        }
        if auto_disarm_receipt:
            details["auto_disarm_receipt"] = auto_disarm_receipt["receipt_path"]

        receipt = _write_receipt(
            receipt_dir=receipt_dir,
            action="submit-order-smoke",
            status="refused-disarmed",
            operator_id=resolved_operator,
            operator_note=operator_note,
            state_file=state_file,
            details=details,
            state=state,
        )
        _append_recent_action(state, receipt)
        save_operator_state(state_file, state)

        payload = {
            "ok": False,
            "error": "order submission refused: runtime is disarmed",
            "gate_reason": submission_gate["reason"],
            "request": request,
            "receipt_path": receipt["receipt_path"],
        }
        if auto_disarm_receipt:
            payload["auto_disarm_receipt"] = auto_disarm_receipt["receipt_path"]

        return OperatorResult(
            payload=payload,
            exit_code=OPERATOR_REFUSED_EXIT,
        )

    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="submit-order-smoke",
        status="accepted-for-smoke-dispatch",
        operator_id=resolved_operator,
        operator_note=operator_note,
        state_file=state_file,
        details={
            "request": request,
            "dispatch": "stub-only; no broker adapter submission in seed runtime",
        },
        state=state,
    )
    _append_recent_action(state, receipt)
    save_operator_state(state_file, state)

    return OperatorResult(
        payload={
            "ok": True,
            "request": request,
            "dispatch": "stub-only; no broker submission executed",
            "receipt_path": receipt["receipt_path"],
        },
        exit_code=0,
    )
