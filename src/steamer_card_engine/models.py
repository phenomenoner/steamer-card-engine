from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


IntentSide = Literal["buy", "sell", "cover", "reduce", "exit"]
IntentType = Literal["enter", "exit", "adjust", "cancel_request"]
CardStatus = Literal["draft", "replay-only", "operator-approved", "retired"]


@dataclass(slots=True)
class Intent:
    intent_id: str
    card_id: str
    symbol: str
    side: IntentSide
    intent_type: IntentType
    reason: str
    confidence: float = 0.0
    size_hint: float | None = None
    tags: tuple[str, ...] = ()


@dataclass(slots=True)
class CardManifest:
    card_id: str
    name: str
    version: str
    strategy_family: str
    status: CardStatus = "draft"
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class DeckManifest:
    deck_id: str
    cards: list[str]
    symbol_scope: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GlobalConfig:
    market: str = "TW_CASH"
    session: str = "intraday"
    live_enabled: bool = False
    dry_run: bool = True
