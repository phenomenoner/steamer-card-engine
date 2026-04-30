from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
import tomllib
from pathlib import Path
from typing import Any
from uuid import uuid4

from steamer_card_engine.manifest import ManifestValidationError, load_auth_profile, load_deck_manifest


OPERATOR_REFUSED_EXIT = 4
OPERATOR_CONFIRMATION_REQUIRED_EXIT = 5

MIN_ARM_TTL_SECONDS = 30
MAX_ARM_TTL_SECONDS = 8 * 60 * 60

STAGE1_REAL_TRADE_GATE_REQUIRED_CARDS = (
    "real-trade-gate-short-first-entry-v1",
    "real-trade-gate-short-first-cover-v1",
)
STAGE1_REAL_TRADE_GATE_POLICY = {
    "stage": "stage1-short-capability-smoke",
    "entry_side": "sell",
    "exit_side": "cover",
    "max_entry_orders_per_run": 1,
    "max_exit_orders_per_run": 1,
    "max_round_trips_per_day": 1,
    "requires_shortable_symbol_allowlist": True,
}


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

    raw = state_file.read_text(encoding="utf-8").strip()
    if not raw:
        return _default_state()

    payload = json.loads(raw)
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


def _load_real_trade_gate_policy(deck_path: str | None) -> dict[str, Any]:
    if not deck_path:
        return {}
    with Path(deck_path).open("rb") as file:
        payload = tomllib.load(file)
    policy = payload.get("policy")
    if not isinstance(policy, dict):
        return {}
    real_trade_gate = policy.get("real_trade_gate")
    if not isinstance(real_trade_gate, dict):
        return {}
    return real_trade_gate


def _stage1_policy_blockers(policy: dict[str, Any]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not policy:
        return [
            {
                "code": "real-trade-gate-policy-missing",
                "detail": "deck must define [policy.real_trade_gate] for Stage 1 planner",
            }
        ]

    for key, expected in STAGE1_REAL_TRADE_GATE_POLICY.items():
        actual = policy.get(key)
        if actual != expected:
            blockers.append(
                {
                    "code": f"stage1-policy-{key.replace('_', '-')}-mismatch",
                    "detail": f"policy.real_trade_gate.{key} must be {expected!r}",
                    "expected": expected,
                    "actual": actual,
                }
            )
    return blockers


def operator_plan_real_trade_gate(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str,
    deck_ref: str,
    symbol: str,
    entry_side: str,
    quantity: int,
    exit_delay_seconds: int,
    shortable_symbols: list[str],
    operator_id: str | None,
    operator_note: str | None,
) -> OperatorResult:
    state = load_operator_state(state_file)
    _apply_auth_profile(state, auth_profile_path=auth_profile_path, session_id=None)
    _maybe_auto_disarm(state=state, state_file=state_file, receipt_dir=receipt_dir)

    resolved_operator = _resolve_operator_id(operator_id)
    request = {
        "deck": deck_ref,
        "symbol": symbol,
        "entry_side": entry_side,
        "quantity": quantity,
        "exit_delay_seconds": exit_delay_seconds,
        "shortable_symbols": sorted(set(shortable_symbols)),
    }

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if entry_side not in {"buy", "sell"}:
        blockers.append({"code": "invalid-entry-side", "detail": "entry_side must be buy or sell"})
    if entry_side != "sell":
        blockers.append(
            {
                "code": "stage1-requires-sell-first",
                "detail": "Stage 1 real-trade gate requires sell-first to prove short/day-trade capability",
            }
        )
    if quantity < 1:
        blockers.append({"code": "invalid-quantity", "detail": "quantity must be >= 1"})
    if exit_delay_seconds < 1:
        blockers.append({"code": "invalid-exit-delay", "detail": "exit_delay_seconds must be >= 1"})

    deck_id: str | None = None
    deck_path: str | None = None
    deck_symbols: list[str] = []
    real_trade_gate_policy: dict[str, Any] = {}
    try:
        deck_id, deck_path = _resolve_deck(deck_ref)
        deck = load_deck_manifest(deck_path)
        deck_symbols = list(deck.symbol_scope)
        actual_cards = list(deck.cards)
        if actual_cards != list(STAGE1_REAL_TRADE_GATE_REQUIRED_CARDS):
            blockers.append(
                {
                    "code": "stage1-deck-card-contract-mismatch",
                    "detail": "Stage 1 planner requires the exact ordered short-first entry then cover card sequence",
                    "expected_cards": list(STAGE1_REAL_TRADE_GATE_REQUIRED_CARDS),
                    "actual_cards": actual_cards,
                }
            )
        real_trade_gate_policy = _load_real_trade_gate_policy(deck_path)
        blockers.extend(_stage1_policy_blockers(real_trade_gate_policy))
        if symbol not in set(deck.symbol_scope):
            blockers.append(
                {
                    "code": "symbol-not-in-deck-scope",
                    "detail": f"symbol {symbol} is not in deck symbol_scope",
                    "deck_symbol_scope": sorted(deck.symbol_scope),
                }
            )
    except FileNotFoundError as error:
        blockers.append({"code": "deck-unresolved", "detail": str(error)})
    except ManifestValidationError as error:
        blockers.append(
            {
                "code": "deck-manifest-invalid",
                "detail": str(error),
                "manifest_type": error.manifest_type,
                "path": str(error.path),
                "errors": list(error.errors),
            }
        )

    if not state["capabilities"].get("trade_enabled"):
        blockers.append({"code": "trade-disabled", "detail": "auth profile trade_enabled=false"})
    if not state["capabilities"].get("account_query_enabled"):
        blockers.append({"code": "account-query-disabled", "detail": "auth profile account_query_enabled=false"})
    if not state["capabilities"].get("marketdata_enabled"):
        blockers.append({"code": "marketdata-disabled", "detail": "auth profile marketdata_enabled=false"})

    if symbol not in set(shortable_symbols):
        blockers.append(
            {
                "code": "short-capability-unproven",
                "detail": "sell-first smoke requires an explicit shortable/daytrade-capable symbol allowlist hit",
                "symbol": symbol,
            }
        )

    if state.get("armed_live"):
        blockers.append({"code": "posture-already-armed", "detail": "planning gate refuses while armed_live=true"})

    status = "planned" if not blockers else "refused"
    configured_exit_side = str(real_trade_gate_policy.get("exit_side") or "cover")
    exit_leg_side = configured_exit_side if configured_exit_side in {"cover", "sell", "buy"} else "cover"
    broker_order_side = "buy" if exit_leg_side == "cover" else exit_leg_side
    details = {
        "request": request,
        "blockers": blockers,
        "warnings": warnings,
        "plan": {
            "stage": "real-trade-gate-stage1-short-capability-smoke",
            "deck_id": deck_id,
            "deck_ref": deck_path,
            "deck_symbol_scope": sorted(deck_symbols),
            "required_cards": list(STAGE1_REAL_TRADE_GATE_REQUIRED_CARDS),
            "real_trade_gate_policy": real_trade_gate_policy,
            "entry_leg": {"side": entry_side, "symbol": symbol, "quantity": quantity},
            "exit_leg": {
                "side": exit_leg_side,
                "broker_order_side": broker_order_side,
                "symbol": symbol,
                "quantity": quantity,
                "delay_seconds_after_entry_terminal": exit_delay_seconds,
            },
            "max_entry_orders_per_run": 1,
            "max_exit_orders_per_run": 1,
            "max_round_trips_per_day": 1,
            "dispatch_boundary": "plan-only; no broker submission executed",
        },
    }
    receipt = _write_receipt(
        receipt_dir=receipt_dir,
        action="plan-real-trade-gate",
        status=status,
        operator_id=resolved_operator,
        operator_note=operator_note,
        state_file=state_file,
        details=details,
        state=state,
    )
    _append_recent_action(state, receipt)
    save_operator_state(state_file, state)

    payload = {
        "ok": not blockers,
        "plan_status": status,
        "activation": "plan-only",
        "boundary": "no broker login, no live arm, no order submission",
        "blockers": blockers,
        "warnings": warnings,
        "plan": details["plan"],
        "receipt_path": receipt["receipt_path"],
    }
    return OperatorResult(payload=payload, exit_code=0 if not blockers else OPERATOR_REFUSED_EXIT)


def operator_live_smoke_readiness(
    *,
    state_file: Path,
    receipt_dir: Path,
    auth_profile_path: str,
    session_id: str | None,
    deck_ref: str,
    ttl_seconds: int,
    symbol: str,
    side: str,
    quantity: int,
    flatten_mode: str,
    operator_id: str | None,
    operator_note: str | None,
) -> OperatorResult:
    steps: list[dict[str, Any]] = []
    armed_window_open = False

    def _fail(error: str, failed_step: dict[str, Any]) -> OperatorResult:
        return OperatorResult(
            payload={
                "ok": False,
                "smoke_status": "fail",
                "activation": "prepared-only",
                "error": error,
                "failed_step": failed_step,
                "steps": steps,
            },
            exit_code=1,
        )

    def _record_step(name: str, result: OperatorResult, *, expect_exit: int, predicate: Any) -> tuple[bool, dict[str, Any]]:
        payload = result.payload
        ok = result.exit_code == expect_exit and bool(predicate(payload))
        step = {
            "step": name,
            "ok": ok,
            "exit_code": result.exit_code,
            "expected_exit_code": expect_exit,
            "payload": payload,
        }
        steps.append(step)
        return ok, step

    status_before = operator_status(
        state_file=state_file,
        receipt_dir=receipt_dir,
        auth_profile_path=auth_profile_path,
        session_id=session_id,
    )
    ok, failed_step = _record_step(
        "status-disarmed-baseline",
        status_before,
        expect_exit=0,
        predicate=lambda payload: payload["armed_live"] is False
        and payload["order_submission_gate"]["allowed"] is False
        and payload["order_submission_gate"]["reason"] == "disarmed-posture",
    )
    if not ok:
        return _fail("baseline disarmed posture did not match contract", failed_step)

    refusal = operator_submit_order_smoke(
        state_file=state_file,
        receipt_dir=receipt_dir,
        auth_profile_path=auth_profile_path,
        session_id=session_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        operator_id=operator_id,
        operator_note=operator_note,
    )
    ok, failed_step = _record_step(
        "submit-refused-while-disarmed",
        refusal,
        expect_exit=OPERATOR_REFUSED_EXIT,
        predicate=lambda payload: payload["ok"] is False and payload.get("gate_reason") == "disarmed-posture",
    )
    if not ok:
        return _fail("disarmed refusal smoke did not match contract", failed_step)

    arm = operator_arm_live(
        state_file=state_file,
        receipt_dir=receipt_dir,
        auth_profile_path=auth_profile_path,
        session_id=session_id,
        deck_ref=deck_ref,
        ttl_seconds=ttl_seconds,
        operator_id=operator_id,
        operator_note=operator_note,
        confirm_live=True,
    )
    ok, failed_step = _record_step(
        "arm-live-bounded-scope",
        arm,
        expect_exit=0,
        predicate=lambda payload: payload["ok"] is True and payload["armed_live"] is True,
    )
    if not ok:
        return _fail("arm-live step did not produce bounded armed posture", failed_step)

    armed_window_open = True
    try:
        acceptance = operator_submit_order_smoke(
            state_file=state_file,
            receipt_dir=receipt_dir,
            auth_profile_path=auth_profile_path,
            session_id=session_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            operator_id=operator_id,
            operator_note=operator_note,
        )
        ok, failed_step = _record_step(
            "submit-accepted-while-armed",
            acceptance,
            expect_exit=0,
            predicate=lambda payload: payload["ok"] is True and "stub-only" in payload.get("dispatch", ""),
        )
        if not ok:
            return _fail("armed smoke dispatch did not produce acceptance receipt", failed_step)

        flatten = operator_flatten(
            state_file=state_file,
            receipt_dir=receipt_dir,
            auth_profile_path=auth_profile_path,
            session_id=session_id,
            mode=flatten_mode,
            operator_id=operator_id,
            operator_note=operator_note,
        )
        ok, failed_step = _record_step(
            "flatten-and-close-armed-window",
            flatten,
            expect_exit=0,
            predicate=lambda payload: payload["ok"] is True and payload["armed_live"] is False,
        )
        if not ok:
            return _fail("flatten step did not close armed posture", failed_step)

        armed_window_open = False
    finally:
        if armed_window_open:
            cleanup = operator_disarm_live(
                state_file=state_file,
                receipt_dir=receipt_dir,
                auth_profile_path=auth_profile_path,
                session_id=session_id,
                operator_id=operator_id,
                operator_note="live-smoke-readiness cleanup disarm after failure",
            )
            _record_step(
                "cleanup-disarm-after-failure",
                cleanup,
                expect_exit=0,
                predicate=lambda payload: payload["ok"] is True and payload["armed_live"] is False,
            )

    status_after = operator_status(
        state_file=state_file,
        receipt_dir=receipt_dir,
        auth_profile_path=auth_profile_path,
        session_id=session_id,
    )
    ok, failed_step = _record_step(
        "status-disarmed-after-flatten",
        status_after,
        expect_exit=0,
        predicate=lambda payload: payload["armed_live"] is False
        and payload["order_submission_gate"]["allowed"] is False
        and payload["order_submission_gate"]["reason"] == "disarmed-posture",
    )
    if not ok:
        return _fail("final disarmed posture did not match contract", failed_step)

    receipt_paths = [
        step["payload"].get("receipt_path")
        for step in steps
        if isinstance(step.get("payload"), dict) and step["payload"].get("receipt_path")
    ]

    return OperatorResult(
        payload={
            "ok": True,
            "smoke_status": "pass",
            "activation": "prepared-only",
            "boundary": "seed smoke/control surface only; no broker submission executed",
            "deck": deck_ref,
            "auth_profile": auth_profile_path,
            "request": {
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            },
            "flatten_mode": flatten_mode,
            "receipt_paths": receipt_paths,
            "steps": steps,
        },
        exit_code=0,
    )
