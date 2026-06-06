from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HandoffValidationError(Exception):
    def __init__(self, path: Path, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.path = path
        self.errors = errors


def _load_packet(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HandoffValidationError(path, [f"packet_load_failed:{exc}"]) from exc
    if not isinstance(payload, dict):
        raise HandoffValidationError(path, ["packet_must_be_object"])
    return payload


def validate_consolidation_handoff(path: Path) -> dict[str, Any]:
    """Validate a Steamer consolidation handoff packet without executing it."""
    payload = _load_packet(path)
    errors: list[str] = []

    if payload.get("schema") != "card_engine_handoff.dry_run.v1":
        errors.append("schema_must_be_card_engine_handoff_dry_run_v1")
    if payload.get("research_only") is not True:
        errors.append("research_only_must_be_true")
    if payload.get("not_trading_advice") is not True:
        errors.append("not_trading_advice_must_be_true")
    if payload.get("order_authority") != "disabled":
        errors.append("order_authority_must_be_disabled")
    if payload.get("live_trading_claim") is not False:
        errors.append("live_trading_claim_must_be_false")
    if not payload.get("session_plan"):
        errors.append("session_plan_ref_missing")

    packet_errors = [str(item) for item in payload.get("validation_errors") or []]
    local_packet_valid = bool(payload.get("local_packet_valid"))
    if local_packet_valid and "session_plan_validation_failed" in packet_errors:
        errors.append("local_packet_valid_conflicts_with_session_plan_failure")
    allowed_replay_pending_errors = {"card_engine_side_validation_not_run"}
    unexpected_replay_pending_errors = sorted(set(packet_errors) - allowed_replay_pending_errors)
    if local_packet_valid and unexpected_replay_pending_errors:
        errors.append(
            "local_packet_valid_has_unresolved_errors:"
            + ",".join(unexpected_replay_pending_errors)
        )
    if payload.get("packet_valid") is True and payload.get("card_engine_side_validation") != "passed":
        errors.append("packet_valid_requires_card_engine_side_validation_passed")

    if errors:
        raise HandoffValidationError(path, errors)

    blocked_no_entry = not local_packet_valid
    status = "blocked_no_entry" if blocked_no_entry else "local_packet_valid_pending_replay"
    no_entry_reasons = sorted(
        {error for error in packet_errors if error != "card_engine_side_validation_not_run"}
    ) if blocked_no_entry else []
    if blocked_no_entry and not no_entry_reasons:
        no_entry_reasons = ["local_packet_valid_false"]

    return {
        "ok": True,
        "schema": "steamer-card-engine-consolidation-handoff-validation.v1",
        "packet": str(path),
        "status": status,
        "handoff_accepted": True,
        "replay_ready": local_packet_valid,
        "no_entry_reasons": no_entry_reasons,
        "order_authority": "disabled",
        "live_trading_claim": False,
    }
