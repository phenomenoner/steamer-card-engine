from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from steamer_card_engine.adapters.base import BrokerReceipt, ExecutionRequest, normalized_broker_reject


@dataclass(frozen=True, slots=True)
class LiveExecutionPolicy:
    """First-live policy for the real-trade gate.

    The policy is intentionally tiny and fail-closed: one symbol allowlist, one
    round trip per day, max 1000 shares, sell-first daytrade mapping only.
    """

    symbol_allowlist: frozenset[str]
    max_quantity: int = 1000
    max_round_trips_per_day: int = 1
    require_sell_first_daytrade: bool = True


@dataclass(frozen=True, slots=True)
class RoundTripPlan:
    plan_id: str
    symbol: str
    quantity: int
    entry: ExecutionRequest
    exit: ExecutionRequest
    broker_mapping: dict[str, Any]
    entry_filter: dict[str, Any] = field(default_factory=dict)
    exit_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RoundTripLedger:
    path: Path

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema_version": "steamer-live-roundtrip-ledger/v1", "days": {}}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"roundtrip ledger must be a JSON object: {self.path}")
        raw.setdefault("schema_version", "steamer-live-roundtrip-ledger/v1")
        raw.setdefault("days", {})
        return raw

    def count_for_day(self, day: date, symbol: str) -> int:
        payload = self.load()
        day_rows = payload.get("days", {}).get(day.isoformat(), [])
        if not isinstance(day_rows, list):
            return 0
        return sum(1 for row in day_rows if isinstance(row, dict) and row.get("symbol") == symbol)

    def count_total_for_day(self, day: date) -> int:
        payload = self.load()
        day_rows = payload.get("days", {}).get(day.isoformat(), [])
        if not isinstance(day_rows, list):
            return 0
        return sum(1 for row in day_rows if isinstance(row, dict))

    def record_closed(self, *, day: date, symbol: str, plan_id: str, receipt_id: str) -> None:
        payload = self.load()
        days = payload.setdefault("days", {})
        rows = days.setdefault(day.isoformat(), [])
        if not isinstance(rows, list):
            rows = []
            days[day.isoformat()] = rows
        rows.append(
            {
                "symbol": symbol,
                "plan_id": plan_id,
                "receipt_id": receipt_id,
                "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclass(frozen=True, slots=True)
class RiskEvaluation:
    allowed: bool
    reason: str
    blockers: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class BrokerRoundTripAdapter(Protocol):
    adapter_id: str

    def execute_round_trip(self, plan: RoundTripPlan) -> dict[str, Any]: ...


class FirstLiveRiskGuard:
    def __init__(self, *, policy: LiveExecutionPolicy, ledger: RoundTripLedger | None = None) -> None:
        self.policy = policy
        self.ledger = ledger

    def evaluate(self, *, symbol: str, quantity: int, today: date | None = None) -> RiskEvaluation:
        blockers: list[dict[str, Any]] = []
        if symbol not in self.policy.symbol_allowlist:
            blockers.append({"code": "symbol-not-allowlisted", "symbol": symbol})
        if quantity <= 0:
            blockers.append({"code": "invalid-quantity", "detail": "quantity must be positive"})
        if quantity > self.policy.max_quantity:
            blockers.append(
                {
                    "code": "quantity-exceeds-policy",
                    "quantity": quantity,
                    "max_quantity": self.policy.max_quantity,
                }
            )
        if self.policy.require_sell_first_daytrade is not True:
            blockers.append({"code": "sell-first-daytrade-required"})
        if self.ledger is not None:
            day = today or datetime.now(UTC).date()
            used = self.ledger.count_total_for_day(day)
            if used >= self.policy.max_round_trips_per_day:
                blockers.append(
                    {
                        "code": "roundtrip-limit-reached",
                        "symbol": symbol,
                        "day": day.isoformat(),
                        "used": used,
                        "max_round_trips_per_day": self.policy.max_round_trips_per_day,
                    }
                )
        return RiskEvaluation(
            allowed=not blockers,
            reason="allowed" if not blockers else "risk-blocked",
            blockers=tuple(blockers),
        )


def build_sell_first_round_trip_plan(
    *, symbol: str, quantity: int, entry_filter: dict[str, Any] | None = None, exit_policy: dict[str, Any] | None = None
) -> RoundTripPlan:
    plan_id = f"rt-{uuid4().hex}"
    entry = ExecutionRequest(
        request_id=f"{plan_id}:entry",
        symbol=symbol,
        side="sell",
        quantity=quantity,
        order_type="daytrade_sell_first_ioc_limit_down",
        execution_mode="live",
        tags=("stage1", "sell-first", "daytrade", "entry"),
    )
    exit_request = ExecutionRequest(
        request_id=f"{plan_id}:exit",
        symbol=symbol,
        side="buy",
        quantity=quantity,
        order_type="stock_buyback_ioc_limit_up",
        execution_mode="live",
        tags=("stage1", "buyback", "exit"),
    )
    return RoundTripPlan(
        plan_id=plan_id,
        symbol=symbol,
        quantity=quantity,
        entry=entry,
        exit=exit_request,
        broker_mapping={
            "entry": {
                "buy_sell": "Sell",
                "market_type": "Common",
                "order_type": "DayTrade",
                "price_type": "Limit",
                "time_in_force": "IOC",
                "price_source": "limitdown_price",
            },
            "exit": {
                "buy_sell": "Buy",
                "market_type": "Common",
                "order_type": "Stock",
                "price_type": "Limit",
                "time_in_force": "IOC",
                "price_source": "limitup_price",
            },
        },
        entry_filter=dict(entry_filter or {}),
        exit_policy=dict(exit_policy or {}),
    )


class DryRunRoundTripAdapter:
    adapter_id = "dry-run-roundtrip"

    def execute_round_trip(self, plan: RoundTripPlan) -> dict[str, Any]:
        return {
            "schema_version": "steamer-live-execution-roundtrip/v1",
            "adapter_id": self.adapter_id,
            "mode": "dry-run",
            "plan_id": plan.plan_id,
            "symbol": plan.symbol,
            "quantity": plan.quantity,
            "dispatch_suppressed": True,
            "status": "dry-run-closed",
            "entry_receipt": BrokerReceipt(
                request_id=plan.entry.request_id,
                status="dry-run-accepted",
                message="entry order translated; broker dispatch suppressed",
                safe_to_replay=True,
            ).to_public_dict(),
            "exit_receipt": BrokerReceipt(
                request_id=plan.exit.request_id,
                status="dry-run-accepted",
                message="buyback order translated; broker dispatch suppressed",
                safe_to_replay=True,
            ).to_public_dict(),
            "broker_mapping": plan.broker_mapping,
            "entry_filter": plan.entry_filter,
            "exit_policy": plan.exit_policy,
        }


def rejected_round_trip_receipt(*, plan: RoundTripPlan, blockers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "steamer-live-execution-roundtrip/v1",
        "mode": "risk-refused",
        "plan_id": plan.plan_id,
        "symbol": plan.symbol,
        "quantity": plan.quantity,
        "status": "refused",
        "blockers": blockers,
        "entry_receipt": normalized_broker_reject(
            request_id=plan.entry.request_id,
            category="capability_mismatch",
            message="risk guard refused entry dispatch",
            retryable=False,
            safe_to_replay=False,
        ).to_public_dict(),
        "exit_receipt": None,
        "entry_filter": plan.entry_filter,
        "exit_policy": plan.exit_policy,
    }
