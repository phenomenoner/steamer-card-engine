from __future__ import annotations

from dataclasses import dataclass, field

from steamer_card_engine.adapters.base import ExecutionRequest, MarketEvent
from steamer_card_engine.models import Intent


@dataclass(slots=True)
class MarketDataHub:
    subscribed_symbols: set[str] = field(default_factory=set)


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
