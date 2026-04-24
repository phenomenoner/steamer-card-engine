from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import re
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
SessionAuthMode = Literal["account_password_cert", "account_api_key_cert", "unknown"]

_PUBLIC_TEXT_LIMIT = 240
_PUBLIC_REF_LIMIT = 120
_SENSITIVE_PUBLIC_TEXT = re.compile(
    r"(?i)(secret|token|password|passwd|api[_-]?key|certificate|private[_-]?key|bearer\s+)"
)


def sanitize_public_text(value: str | None, *, limit: int = _PUBLIC_TEXT_LIMIT) -> str | None:
    """Return bounded public text with obvious secret-bearing content redacted."""

    if value is None:
        return None
    normalized = " ".join(str(value).split())
    if not normalized:
        return ""
    if _SENSITIVE_PUBLIC_TEXT.search(normalized):
        return "[redacted]"
    if len(normalized) > limit:
        return f"{normalized[: limit - 1]}…"
    return normalized


def sanitize_public_ref(value: str | None, *, limit: int = _PUBLIC_REF_LIMIT) -> str | None:
    """Return an opaque, bounded public reference suitable for local lookup."""

    sanitized = sanitize_public_text(value, limit=limit)
    if sanitized is None or sanitized == "[redacted]":
        return sanitized
    return re.sub(r"[^A-Za-z0-9:._/@#=-]", "_", sanitized)[:limit]


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
class SessionCapabilityEnvelope:
    marketdata_enabled: bool = False
    account_query_enabled: bool = False
    trade_enabled: bool = False
    paper_trading_enabled: bool = False
    live_trading_enabled: bool = False
    supported_actions: tuple[str, ...] = ()
    degraded_reason: str | None = None

    def allows_marketdata(self) -> bool:
        return self.marketdata_enabled

    def allows_account_query(self, action: str = "positions") -> bool:
        return self.account_query_enabled and action in self.supported_actions

    def allows_trade_action(self, action: str, mode: ExecutionMode = "paper") -> bool:
        if action not in self.supported_actions or not self.trade_enabled:
            return False
        if mode == "paper":
            return self.paper_trading_enabled
        if mode == "live":
            return self.live_trading_enabled
        return False

    def to_public_dict(self) -> dict[str, object]:
        return {
            "marketdata_enabled": self.marketdata_enabled,
            "account_query_enabled": self.account_query_enabled,
            "trade_enabled": self.trade_enabled,
            "paper_trading_enabled": self.paper_trading_enabled,
            "live_trading_enabled": self.live_trading_enabled,
            "supported_actions": self.supported_actions,
            "degraded_reason": sanitize_public_text(self.degraded_reason),
        }


@dataclass(frozen=True, slots=True)
class SessionContext:
    session_id: str
    auth_mode: SessionAuthMode = "unknown"
    authenticated: bool = False
    health_status: str = "unknown"
    capabilities: SessionCapabilityEnvelope = field(default_factory=SessionCapabilityEnvelope)
    session_started_at: datetime | None = None
    expires_at: datetime | None = None
    renewal_hint: str | None = None
    account_scope: str = "<ACCOUNT_SCOPE>"
    vendor_metadata: dict[str, str] = field(default_factory=dict)

    def allows_marketdata(self) -> bool:
        return self.authenticated and self.capabilities.allows_marketdata()

    def allows_account_query(self, action: str = "positions") -> bool:
        return self.authenticated and self.capabilities.allows_account_query(action)

    def allows_trade_action(self, action: str, mode: ExecutionMode = "paper") -> bool:
        return self.authenticated and self.capabilities.allows_trade_action(action, mode)

    def to_public_dict(self) -> dict[str, object]:
        return {
            "session_id": sanitize_public_ref(self.session_id),
            "auth_mode": self.auth_mode,
            "authenticated": self.authenticated,
            "health_status": sanitize_public_text(self.health_status),
            "capabilities": self.capabilities.to_public_dict(),
            "session_started_at": self.session_started_at.isoformat() if self.session_started_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "renewal_hint": sanitize_public_text(self.renewal_hint),
            "account_scope": sanitize_public_ref(self.account_scope),
            "vendor_metadata": {
                sanitize_public_ref(key) or "metadata": sanitize_public_text(value)
                for key, value in self.vendor_metadata.items()
            },
        }


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
        if mode == "paper":
            return self.paper_trading_enabled
        return False


@dataclass(frozen=True, slots=True)
class SubmitPreflightDecision:
    allowed: bool
    category: BrokerErrorCategory | None = None
    reason: str = ""
    session_allows: bool = False
    broker_allows: bool = False
    action: str = "submit"
    execution_mode: str = "paper"

    def to_receipt(self, request_id: str, *, receipt_id: str | None = None) -> BrokerReceipt:
        if self.allowed:
            return BrokerReceipt(
                request_id=request_id,
                status="preflight_allowed",
                message=sanitize_public_text(self.reason) or "submit preflight allowed",
                receipt_id=receipt_id,
            )
        return normalized_broker_reject(
            request_id=request_id,
            category=self.category or "capability_mismatch",
            message=self.reason or "submit preflight failed closed",
            retryable=False,
            safe_to_replay=True,
            raw_ref="preflight:submit-capability-mismatch",
            receipt_id=receipt_id,
        )


def broker_submit_preflight(
    *,
    session: SessionContext | None,
    broker: BrokerCapabilityProfile,
    request: ExecutionRequest,
) -> SubmitPreflightDecision:
    mode = request.execution_mode
    if mode not in {"paper", "live"}:
        return SubmitPreflightDecision(
            allowed=False,
            category="capability_mismatch",
            reason="unknown execution mode is not permitted for broker submit",
            execution_mode=str(mode),
        )
    if session is None or not session.authenticated:
        return SubmitPreflightDecision(
            allowed=False,
            category="auth",
            reason="authenticated logical session is required for broker submit",
            execution_mode=mode,
        )

    session_allows = session.allows_trade_action("submit", mode)
    broker_allows = broker.allows("submit", mode)
    if session_allows and broker_allows:
        return SubmitPreflightDecision(
            allowed=True,
            reason="session and broker capability profile allow submit",
            session_allows=True,
            broker_allows=True,
            execution_mode=mode,
        )
    return SubmitPreflightDecision(
        allowed=False,
        category="capability_mismatch",
        reason="session and broker capability profile do not both allow submit",
        session_allows=session_allows,
        broker_allows=broker_allows,
        execution_mode=mode,
    )


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
            "message": sanitize_public_text(self.message),
            "retryable": self.retryable,
            "safe_to_replay": self.safe_to_replay,
            "raw_ref": sanitize_public_ref(self.raw_ref),
            "receipt_id": sanitize_public_ref(self.receipt_id),
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
            "request_id": sanitize_public_ref(self.request_id),
            "status": self.status,
            "broker_order_id": sanitize_public_ref(self.broker_order_id),
            "message": sanitize_public_text(self.message),
            "retryable": self.retryable,
            "safe_to_replay": self.safe_to_replay,
            "raw_ref": sanitize_public_ref(self.raw_ref),
            "receipt_id": sanitize_public_ref(self.receipt_id),
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
