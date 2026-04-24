from __future__ import annotations

from dataclasses import dataclass, field

from steamer_card_engine.adapters.base import ExecutionRequest, MarketEvent
from steamer_card_engine.models import Intent


_ALLOWED_CONNECTION_STATES = frozenset(
    {"unknown", "disconnected", "connecting", "connected", "degraded", "replaying"}
)
_ALLOWED_STALE_REASONS = frozenset(
    {"source_idle", "lag_exceeded", "disconnected", "replay_gap", "unknown"}
)
_ALLOWED_ERROR_CLASSES = frozenset(
    {"parse_error", "schema_mismatch", "stale_source", "adapter_error", "unknown"}
)


def _bounded_value(value: str | None, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None
    return value if value in allowed else "unknown"


@dataclass(frozen=True, slots=True)
class MarketDataHubStats:
    """Aggregate-only MarketDataHub introspection seed.

    Keep this shape privacy-preserving: counts and bounded health facts only, no
    raw symbols, subscriber identities, account data, or event payloads.
    """

    schema_version: str = "market-data-hub-stats/v1"
    connection_state: str = "unknown"
    subscription_count: int = 0
    subscriber_count: int = 0
    event_count: int = 0
    last_event_at_utc: str | None = None
    stale: bool = False
    stale_reason: str | None = None
    error_count: int = 0
    last_error_class: str | None = None


@dataclass(slots=True)
class MarketDataHub:
    subscribed_symbols: set[str] = field(default_factory=set)
    subscriber_count: int = 0
    event_count: int = 0
    last_event_at_utc: str | None = None
    connection_state: str = "unknown"
    stale: bool = False
    stale_reason: str | None = None
    error_count: int = 0
    last_error_class: str | None = None

    def stats(self) -> MarketDataHubStats:
        """Return aggregate-only stats without leaking symbol/subscriber identities."""

        return MarketDataHubStats(
            connection_state=_bounded_value(self.connection_state, _ALLOWED_CONNECTION_STATES)
            or "unknown",
            subscription_count=len(self.subscribed_symbols),
            subscriber_count=self.subscriber_count,
            event_count=self.event_count,
            last_event_at_utc=self.last_event_at_utc,
            stale=self.stale,
            stale_reason=_bounded_value(self.stale_reason, _ALLOWED_STALE_REASONS),
            error_count=self.error_count,
            last_error_class=_bounded_value(self.last_error_class, _ALLOWED_ERROR_CLASSES),
        )


@dataclass(slots=True)
class CardRuntime:
    loaded_cards: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IntentAggregator:
    recent_intents: list[Intent] = field(default_factory=list)

    def accept(self, intent: Intent) -> None:
        self.recent_intents.append(intent)


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    reason: str


@dataclass(slots=True)
class RiskGuard:
    def evaluate(self, intent: Intent) -> RiskDecision:
        return RiskDecision(allowed=False, reason="risk policy not implemented yet")


@dataclass(slots=True)
class ExecutionEngine:
    submitted: list[ExecutionRequest] = field(default_factory=list)


@dataclass(slots=True)
class ReplayRunner:
    processed_events: int = 0

    def feed(self, event: MarketEvent) -> None:
        self.processed_events += 1
