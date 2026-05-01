from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from steamer_card_engine.adapters.base import (
    BrokerCapabilityProfile,
    BrokerReceipt,
    ExecutionRequest,
    SessionCapabilityEnvelope,
    SessionContext,
    broker_submit_preflight,
)


FIXTURE_PROBE_SCHEMA_VERSION = "adapter-probe/v0"
FIXTURE_CONTRACT_SCHEMA_VERSION = "adapter-contract/v1"
FIXTURE_CONTRACT_FIXTURE_SCHEMA_VERSION = "adapter-contract-fixtures/v1"
FIXTURE_REPLAY_SCHEMA_VERSION = "adapter-replay/v1"
FIXTURE_ADAPTER_ID = "fixture-paper-only"
FIXTURE_ADAPTER_VENDOR = "fixture"
FIXTURE_ADAPTER_VERSION = "v0"
FIXTURE_DISPATCH_BOUNDARY = "fixture-only; no broker SDK; no live order"
FIXTURE_CONTRACT_INPUT_HASH = "fixture-paper-only:v0:adapter-contract"


def _stable_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FixtureAdapterIdentity:
    id: str = FIXTURE_ADAPTER_ID
    vendor: str = FIXTURE_ADAPTER_VENDOR
    version: str = FIXTURE_ADAPTER_VERSION

    def to_public_dict(self) -> dict[str, str]:
        return {"id": self.id, "vendor": self.vendor, "version": self.version}


class FixturePaperOnlyAdapter:
    """Deterministic fixture broker adapter for contract probing only.

    This adapter intentionally has no broker SDK, network, env, credential, or state-file
    dependencies. It exists to prove public contract shape and fail-closed behavior.
    """

    adapter_id = FIXTURE_ADAPTER_ID
    identity = FixtureAdapterIdentity()

    def __init__(self) -> None:
        self.capabilities = BrokerCapabilityProfile(
            marketdata_enabled=True,
            account_query_enabled=False,
            trade_enabled=True,
            paper_trading_enabled=True,
            live_trading_enabled=False,
            supported_actions=("submit", "cancel"),
            rate_limit_policy="fixture deterministic; no transport",
            credential_permission_state="fixture-paper-only",
        )
        self.session = SessionContext(
            session_id="fixture:paper-only",
            auth_mode="unknown",
            authenticated=True,
            health_status="fixture-only",
            capabilities=SessionCapabilityEnvelope(
                marketdata_enabled=True,
                account_query_enabled=False,
                trade_enabled=True,
                paper_trading_enabled=True,
                live_trading_enabled=False,
                supported_actions=("submit", "cancel"),
            ),
            account_scope="fixture-public-scope",
        )

    def submit(self, request: ExecutionRequest) -> BrokerReceipt:
        decision = broker_submit_preflight(
            session=self.session,
            broker=self.capabilities,
            request=request,
        )
        if not decision.allowed:
            return decision.to_receipt(
                request.request_id,
                receipt_id=f"receipt:{request.request_id}",
            )
        return BrokerReceipt(
            request_id=request.request_id,
            status="preflight_allowed",
            message="fixture paper-only preflight allowed; dispatch suppressed",
            retryable=False,
            safe_to_replay=True,
            raw_ref="fixture:paper-only",
            receipt_id=f"receipt:{request.request_id}",
        )

    def cancel(self, broker_order_id: str) -> BrokerReceipt:
        return BrokerReceipt(
            request_id=broker_order_id,
            status="preflight_allowed",
            message="fixture cancel preflight allowed; dispatch suppressed",
            retryable=False,
            safe_to_replay=True,
            raw_ref="fixture:paper-only",
            receipt_id=f"receipt:{broker_order_id}",
        )

    def iter_order_events(self) -> Iterable[object]:
        return ()


def fixture_capabilities_public_dict(profile: BrokerCapabilityProfile) -> dict[str, object]:
    return {
        "marketdata_enabled": profile.marketdata_enabled,
        "account_query_enabled": profile.account_query_enabled,
        "trade_enabled": profile.trade_enabled,
        "paper_trading_enabled": profile.paper_trading_enabled,
        "live_trading_enabled": profile.live_trading_enabled,
        "supported_actions": list(profile.supported_actions),
        "rate_limit_policy": profile.rate_limit_policy,
        "credential_permission_state": profile.credential_permission_state,
    }


def fixture_contract_schema() -> dict[str, object]:
    """Return the machine-readable Stage 1 fixture adapter contract."""

    return {
        "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
        "input_context": {
            "required": ["card_id", "deck_id", "symbol", "side", "quantity", "execution_mode", "signal"],
            "fields": {
                "card_id": "public card reference string",
                "deck_id": "public deck reference string",
                "symbol": "public symbol placeholder/reference string",
                "side": "buy|sell",
                "quantity": "non-negative integer; 0 is no-op candidate only",
                "execution_mode": "paper|live; unknown modes fail closed",
                "signal": {
                    "action": "enter|exit|hold",
                    "confidence": "number from 0.0 to 1.0",
                    "reason": "public stable signal reason string",
                },
            },
        },
        "normalized_signal": {
            "required": ["action", "decision", "reason_code", "stable_reason"],
            "decisions": ["allow", "reject", "noop"],
            "reason_codes": [
                "paper_preflight_allowed",
                "capability_mismatch",
                "signal_no_action",
                "invalid_quantity",
                "unknown_execution_mode",
            ],
        },
        "order_intent_candidate": {
            "kind": "normalized_order_intent_candidate",
            "broker_native_order": None,
            "fields": ["request_id", "symbol", "side", "quantity", "order_type", "execution_mode", "tags"],
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        },
        "reject_or_noop_reason": {
            "required": ["decision", "reason_code", "stable_reason", "retryable", "safe_to_replay"],
            "stable_reason_required": True,
        },
        "capability_profile": {
            "adapter_id": FIXTURE_ADAPTER_ID,
            "profile": fixture_capabilities_public_dict(FixturePaperOnlyAdapter().capabilities),
        },
        "receipt_envelope": {
            "required": ["schema_version", "adapter", "case_id", "decision", "receipt", "dispatch"],
            "normalized": True,
            "broker_native_orders_allowed": False,
        },
        "sanitizer_contract": {
            "public_text_limit": 240,
            "public_ref_limit": 120,
            "redaction_marker": "[redacted]",
            "redacts_secret_like_text": True,
            "redacts_vendor_native_payload_text": True,
        },
        "no_network": True,
        "topology_changed": False,
    }


def build_fixture_explain_payload(*, adapter_id: str) -> tuple[dict[str, object], int]:
    if adapter_id != FIXTURE_ADAPTER_ID:
        return {
            "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
            "adapter": {"id": adapter_id, "vendor": "fixture", "version": "unknown"},
            "decision": "reject",
            "reason_code": "unknown_adapter",
            "stable_reason": "unknown adapter is not permitted for fixture contract explain",
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
            "topology_changed": False,
            "no_network": True,
        }, 4

    adapter = FixturePaperOnlyAdapter()
    contract = fixture_contract_schema()
    payload = {
        "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
        "adapter": adapter.identity.to_public_dict(),
        "capabilities": fixture_capabilities_public_dict(adapter.capabilities),
        "contract": contract,
        "input_hash": FIXTURE_CONTRACT_INPUT_HASH,
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "topology_changed": False,
        "no_network": True,
    }
    return payload, 0


def _request_from_context(case_id: str, context: dict[str, object]) -> ExecutionRequest:
    return ExecutionRequest(
        request_id=f"contract:{case_id}",
        symbol=str(context.get("symbol", "<FIXTURE_SYMBOL>")),
        side=str(context.get("side", "buy")),  # type: ignore[arg-type]
        quantity=int(context.get("quantity", 0)),
        execution_mode=str(context.get("execution_mode", "paper")),  # type: ignore[arg-type]
        tags=("fixture-contract",),
    )


def evaluate_fixture_contract_case(case: dict[str, object]) -> dict[str, object]:
    adapter = FixturePaperOnlyAdapter()
    case_id = str(case.get("case_id", "unnamed-case"))
    context = case.get("input_context")
    if not isinstance(context, dict):
        context = {}
    signal = context.get("signal") if isinstance(context.get("signal"), dict) else {}
    action = str(signal.get("action", "hold")) if isinstance(signal, dict) else "hold"
    request = _request_from_context(case_id, context)

    if action == "hold" or request.quantity == 0:
        decision = "noop"
        reason_code = "signal_no_action"
        stable_reason = "signal action does not request an order intent"
        receipt = BrokerReceipt(
            request_id=request.request_id,
            status="noop",
            message=stable_reason,
            retryable=False,
            safe_to_replay=True,
            raw_ref="fixture:contract-noop",
            receipt_id=f"receipt:{request.request_id}",
        )
        order_intent: dict[str, object] | None = None
    else:
        preflight = broker_submit_preflight(
            session=adapter.session,
            broker=adapter.capabilities,
            request=request,
        )
        receipt = adapter.submit(request)
        if preflight.allowed:
            decision = "allow"
            reason_code = "paper_preflight_allowed"
            stable_reason = "fixture paper-only capability allows normalized paper intent"
        else:
            decision = "reject"
            reason_code = preflight.category or "capability_mismatch"
            stable_reason = preflight.reason or "fixture contract failed closed before dispatch"
        order_intent = {
            "kind": "normalized_order_intent_candidate",
            "request_id": request.request_id,
            "symbol": request.symbol,
            "side": request.side,
            "quantity": request.quantity,
            "order_type": request.order_type,
            "execution_mode": request.execution_mode,
            "tags": list(request.tags),
            "broker_native_order": None,
            "dispatch_suppressed": True,
        }

    public_receipt = receipt.to_public_dict()
    return {
        "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
        "adapter": adapter.identity.to_public_dict(),
        "case_id": case_id,
        "input_hash": _stable_hash(context),
        "normalized_signal": {
            "action": action,
            "decision": decision,
            "reason_code": reason_code,
            "stable_reason": stable_reason,
        },
        "order_intent_candidate": order_intent,
        "reject_or_noop_reason": None
        if decision == "allow"
        else {
            "decision": decision,
            "reason_code": reason_code,
            "stable_reason": stable_reason,
            "retryable": False,
            "safe_to_replay": True,
        },
        "receipt": {
            "status": "ok" if decision == "allow" else decision,
            "normalized": True,
            "public": public_receipt,
        },
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "broker_native_orders": [],
        "topology_changed": False,
        "no_network": True,
    }



def _fixture_cases_payload(fixtures_path: Path) -> tuple[Path, dict[str, object], list[dict[str, object]]]:
    cases_file = fixtures_path / "cases.json" if fixtures_path.is_dir() else fixtures_path
    fixture_payload = json.loads(cases_file.read_text(encoding="utf-8"))
    cases_raw = fixture_payload.get("cases", [])
    cases = [case for case in cases_raw if isinstance(case, dict)] if isinstance(cases_raw, list) else []
    return cases_file, fixture_payload, cases


def _adapter_stable_hash() -> str:
    adapter = FixturePaperOnlyAdapter()
    return _stable_hash(
        {
            "adapter": adapter.identity.to_public_dict(),
            "capabilities": fixture_capabilities_public_dict(adapter.capabilities),
            "contract": fixture_contract_schema(),
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        }
    )

def build_fixture_contract_check_payload(
    *, adapter_id: str, fixtures_path: Path
) -> tuple[dict[str, object], int]:
    if adapter_id != FIXTURE_ADAPTER_ID:
        return {
            "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
            "adapter": {"id": adapter_id, "vendor": "fixture", "version": "unknown"},
            "decision": "reject",
            "reason_code": "unknown_adapter",
            "stable_reason": "unknown adapter is not permitted for fixture contract check",
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
            "topology_changed": False,
            "no_network": True,
        }, 4

    cases_file, fixture_payload, cases = _fixture_cases_payload(fixtures_path)
    results = [evaluate_fixture_contract_case(case) for case in cases]
    failures: list[dict[str, object]] = []
    for case, result in zip(cases, results, strict=False):
        expect = case.get("expect", {}) if isinstance(case, dict) else {}
        if not isinstance(expect, dict):
            expect = {}
        signal = result["normalized_signal"]
        if not isinstance(signal, dict):
            continue
        if expect.get("decision") not in {None, signal.get("decision")} or expect.get("reason_code") not in {
            None,
            signal.get("reason_code"),
        }:
            failures.append(
                {
                    "case_id": result["case_id"],
                    "expected": expect,
                    "actual": {
                        "decision": signal.get("decision"),
                        "reason_code": signal.get("reason_code"),
                    },
                }
            )

    payload = {
        "schema_version": FIXTURE_CONTRACT_SCHEMA_VERSION,
        "fixture_schema_version": fixture_payload.get("schema_version"),
        "adapter": FixturePaperOnlyAdapter().identity.to_public_dict(),
        "fixtures": str(cases_file),
        "contract": fixture_contract_schema(),
        "cases": results,
        "summary": {
            "checked": len(results),
            "failed": len(failures),
            "decision": "pass" if not failures else "fail",
        },
        "failures": failures,
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "topology_changed": False,
        "no_network": True,
    }
    return payload, 0 if not failures else 4



def build_fixture_replay_payload(*, adapter_id: str, fixtures_path: Path) -> tuple[dict[str, object], int]:
    """Replay fixture adapter contract cases as a deterministic simulation-only stream."""

    if adapter_id != FIXTURE_ADAPTER_ID:
        return {
            "schema_version": FIXTURE_REPLAY_SCHEMA_VERSION,
            "adapter": {"id": adapter_id, "vendor": "fixture", "version": "unknown"},
            "decision": "reject",
            "reason_code": "unknown_adapter",
            "stable_reason": "unknown adapter is not permitted for fixture replay",
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
            "topology_changed": False,
            "no_network": True,
        }, 4

    cases_file, fixture_payload, cases = _fixture_cases_payload(fixtures_path)
    decisions: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        result = evaluate_fixture_contract_case(case)
        intent = result.get("order_intent_candidate")
        simulation_intent: dict[str, object] | None = None
        if isinstance(intent, dict):
            simulation_intent = dict(intent)
            simulation_intent["simulation_only"] = True
            simulation_intent["intent_mode"] = "replay-simulation"
            simulation_intent["dispatch_suppressed"] = True
            simulation_intent["broker_native_order"] = None
        decisions.append(
            {
                "sequence": index,
                "case_id": result.get("case_id"),
                "input_hash": result.get("input_hash"),
                "normalized_signal": result.get("normalized_signal"),
                "simulation_intent": simulation_intent,
                "receipt": result.get("receipt"),
                "dispatch": result.get("dispatch"),
                "broker_native_orders": [],
            }
        )

    fixture_hash = _stable_hash(fixture_payload)
    replay_range_hash = _stable_hash(
        {
            "fixtures": str(cases_file),
            "case_ids": [decision["case_id"] for decision in decisions],
            "input_hashes": [decision["input_hash"] for decision in decisions],
        }
    )
    adapter_hash = _adapter_stable_hash()
    replay_hash = _stable_hash(
        {
            "schema_version": FIXTURE_REPLAY_SCHEMA_VERSION,
            "adapter_hash": adapter_hash,
            "fixture_hash": fixture_hash,
            "replay_range_hash": replay_range_hash,
            "decisions": decisions,
        }
    )
    summary = {
        "decision": "pass",
        "events": len(decisions),
        "allow": sum(1 for d in decisions if (d.get("normalized_signal") or {}).get("decision") == "allow"),
        "reject": sum(1 for d in decisions if (d.get("normalized_signal") or {}).get("decision") == "reject"),
        "noop": sum(1 for d in decisions if (d.get("normalized_signal") or {}).get("decision") == "noop"),
        "simulation_only_intents": True,
        "broker_native_order_count": 0,
    }
    payload = {
        "schema_version": FIXTURE_REPLAY_SCHEMA_VERSION,
        "fixture_schema_version": fixture_payload.get("schema_version"),
        "adapter": FixturePaperOnlyAdapter().identity.to_public_dict(),
        "fixtures": str(cases_file),
        "mode": "replay",
        "execution": "simulation-only",
        "hashes": {
            "replay_hash": replay_hash,
            "replay_range_hash": replay_range_hash,
            "fixture_hash": fixture_hash,
            "adapter_hash": adapter_hash,
            "input_hash": _stable_hash({"fixture_hash": fixture_hash, "adapter_hash": adapter_hash}),
        },
        "summary": summary,
        "decisions": decisions,
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "broker_native_orders": [],
        "live_readiness_claim": False,
        "topology_changed": False,
        "no_network": True,
    }
    return payload, 0

def build_fixture_probe_payload(*, fixture: str, execution_mode: str) -> tuple[dict[str, object], int]:
    if fixture != "paper-only":
        payload: dict[str, object] = {
            "adapter": {"id": fixture, "vendor": "fixture", "version": "unknown"},
            "session_posture": "fixture_only",
            "preflight": {
                "decision": "reject",
                "execution_mode": execution_mode,
                "reason": "unknown fixture is not permitted for adapter probe",
            },
            "receipt": {
                "status": "rejected",
                "normalized": True,
                "raw_ref": "fixture:unknown",
            },
            "dispatch": FIXTURE_DISPATCH_BOUNDARY,
            "topology_changed": False,
            "schema_version": FIXTURE_PROBE_SCHEMA_VERSION,
            "no_network": True,
        }
        return payload, 4

    adapter = FixturePaperOnlyAdapter()
    request = ExecutionRequest(
        request_id="fixture-probe-paper-only",
        symbol="<FIXTURE_SYMBOL>",
        side="buy",
        quantity=1,
        execution_mode=execution_mode,  # type: ignore[arg-type]
    )
    decision = broker_submit_preflight(
        session=adapter.session,
        broker=adapter.capabilities,
        request=request,
    )
    receipt = adapter.submit(request)

    if decision.allowed:
        reason = "fixture paper-only capability allows paper preflight"
        decision_label = "allow"
        exit_code = 0
    else:
        reason = decision.reason or "fixture probe failed closed before dispatch"
        decision_label = "reject"
        exit_code = 4

    payload = {
        "adapter": adapter.identity.to_public_dict(),
        "capabilities": fixture_capabilities_public_dict(adapter.capabilities),
        "session_posture": "fixture_only",
        "preflight": {
            "decision": decision_label,
            "execution_mode": execution_mode,
            "reason": reason,
            "session_allows": decision.session_allows,
            "broker_allows": decision.broker_allows,
        },
        "receipt": {
            "status": "ok" if decision.allowed else "rejected",
            "normalized": True,
            "raw_ref": receipt.to_public_dict()["raw_ref"] or "fixture:paper-only",
            "public": receipt.to_public_dict(),
        },
        "dispatch": FIXTURE_DISPATCH_BOUNDARY,
        "topology_changed": False,
        "schema_version": FIXTURE_PROBE_SCHEMA_VERSION,
        "input_hash": "fixture-paper-only:v0:paper-probe",
        "no_network": True,
    }
    return payload, exit_code
