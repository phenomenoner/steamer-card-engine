from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from steamer_card_engine.models import Intent


@dataclass(slots=True)
class MarketContext:
    symbol: str
    last_price: float
    tags: tuple[str, ...] = field(default_factory=tuple)
    features: dict[str, float] = field(default_factory=dict)


class Card(ABC):
    card_id: str
    version: str

    @abstractmethod
    def on_event(self, context: MarketContext) -> list[Intent]:
        """Return zero or more intents for the current event."""
