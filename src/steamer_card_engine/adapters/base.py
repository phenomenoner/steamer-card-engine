from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Literal


ConnectionState = Literal["connected", "connecting", "disconnected", "not-connected", "degraded", "error"]
BrokerErrorCategory = Literal[
    "auth",
    "insufficient_funds",
    "invalid_order",
    "rate_limit",
    "network",
    "unavailable",
    "capability_mismatch",
    "unknown",
]
ExecutionMode = Literal["paper", "live"]


@dataclass(slots=True)
class ConnectionHealth:
    surface: Literal["marketdata", "broker", "account"]
    state: ConnectionState
    detail: str
    last_heartbeat_at: datetime | None = None
    last_error: str | None = None


@dataclass(slots=True)
class SessionStatus:
    session_state: str
    renewal_state: str
    connected_surfaces: tuple[str, ...] = ()
    degraded_surfaces: tuple[str, ...] = ()


@dataclass(slots=True)
class AdapterHealthSnapshot:
    adapter_id: str
    vendor: str
    version: str
    capabilities: dict[str, bool]
    session_status: SessionStatus
    connections: tuple[ConnectionHealth, ...]


@dataclass(frozen=True, slots=True)
class BrokerCapabilityProfile:
    marketdata_enabled: bool = False
    account_query_enabled: bool = False
    trade_enabled: bool = False
    paper_trading_enabled: bool = False
    live_trading_enabled: bool = False
    supported_actions: tuple[str, ...] = ()
    rate_limit_policy: str | None = None
    credential_permission_state: str = "unknown"

    def allows(self, action: str, mode: ExecutionMode = "paper") -> bool:
        if action not in self.supported_actions:
            return False
        if action in {"positions", "balances", "account"}:
            return self.account_query_enabled
        if action in {"submit", "cancel", "replace"} and not self.trade_enabled:
            return False
        if mode == "live":
            return self.live_trading_enabled
        return self.paper_trading_enabled


@dataclass(frozen=True, slots=True)
class BrokerErrorEnvelope:
    category: BrokerErrorCategory
    message: str
    retryable: bool
    safe_to_replay: bool
    raw_ref: str | None = None
    receipt_id: str | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "category": self.category,
            "message": self.message,
            "retryable": self.retryable,
            "safe_to_replay": self.safe_to_replay,
            "raw_ref": self.raw_ref,
            "receipt_id": self.receipt_id,
        }


@dataclass(slots=True)
class MarketEvent:
    event_id: str
    symbol: str
    event_type: Literal["tick", "quote", "trade", "session"]
    last_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    volume: float | None = None
    source: str = "unknown"


@dataclass(slots=True)
class ExecutionRequest:
    request_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: int
    order_type: str = "market"
    execution_mode: ExecutionMode = "paper"
    tags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class BrokerReceipt:
    request_id: str
    status: str
    broker_order_id: str | None = None
    message: str = ""
    retryable: bool = False
    safe_to_replay: bool = False
    raw_ref: str | None = None
    receipt_id: str | None = None
    error: BrokerErrorEnvelope | None = None

    def to_public_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "broker_order_id": self.broker_order_id,
            "message": self.message,
            "retryable": self.retryable,
            "safe_to_replay": self.safe_to_replay,
            "raw_ref": self.raw_ref,
            "receipt_id": self.receipt_id,
            "error": self.error.to_public_dict() if self.error else None,
        }


def normalized_broker_reject(
    *,
    request_id: str,
    category: BrokerErrorCategory,
    message: str,
    retryable: bool,
    safe_to_replay: bool,
    raw_ref: str | None = None,
    receipt_id: str | None = None,
) -> BrokerReceipt:
    error = BrokerErrorEnvelope(
        category=category,
        message=message,
        retryable=retryable,
        safe_to_replay=safe_to_replay,
        raw_ref=raw_ref,
        receipt_id=receipt_id,
    )
    return BrokerReceipt(
        request_id=request_id,
        status="rejected",
        message=message,
        retryable=retryable,
        safe_to_replay=safe_to_replay,
        raw_ref=raw_ref,
        receipt_id=receipt_id,
        error=error,
    )


class MarketDataAdapter(ABC):
    adapter_id: str

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def subscribe(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    def unsubscribe(self, symbols: list[str]) -> None:
        pass

    @abstractmethod
    def iter_events(self) -> Iterable[MarketEvent]:
        pass


class BrokerAdapter(ABC):
    adapter_id: str

    @abstractmethod
    def submit(self, request: ExecutionRequest) -> BrokerReceipt:
        pass

    @abstractmethod
    def cancel(self, broker_order_id: str) -> BrokerReceipt:
        pass
