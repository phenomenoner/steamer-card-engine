from __future__ import annotations

from dataclasses import dataclass

from steamer_card_engine.cards.base import Card, MarketContext
from steamer_card_engine.models import Intent


@dataclass(slots=True)
class ValidationSmokeCard(Card):
    card_id: str
    version: str
    symbol: str
    trigger_tag: str
    side: str
    intent_type: str
    reason: str
    require_position_open: bool = False

    def on_event(self, context: MarketContext) -> list[Intent]:
        if context.symbol != self.symbol:
            return []
        if self.trigger_tag not in context.tags:
            return []
        if self.require_position_open and "position_open" not in context.tags:
            return []
        return [
            Intent(
                intent_id=f"{self.card_id}:{self.intent_type}:{context.symbol}",
                card_id=self.card_id,
                symbol=context.symbol,
                side=self.side,
                intent_type=self.intent_type,
                reason=self.reason,
                confidence=1.0,
                size_hint=1.0,
                tags=("validation-smoke", self.trigger_tag),
            )
        ]


@dataclass(slots=True)
class NoTradeGuardCard(Card):
    card_id: str
    version: str

    def on_event(self, context: MarketContext) -> list[Intent]:
        return []


def entry_once() -> Card:
    return ValidationSmokeCard(
        card_id="smoke-entry-once-v1",
        version="0.1.0",
        symbol="2330",
        trigger_tag="entry_once",
        side="buy",
        intent_type="enter",
        reason="validation smoke entry triggered",
    )


def exit_once() -> Card:
    return ValidationSmokeCard(
        card_id="smoke-exit-once-v1",
        version="0.1.0",
        symbol="2330",
        trigger_tag="exit_once",
        side="exit",
        intent_type="exit",
        reason="validation smoke exit triggered",
        require_position_open=True,
    )


def no_trade_guard() -> Card:
    return NoTradeGuardCard(
        card_id="smoke-no-trade-guard-v1",
        version="0.1.0",
    )


def short_first_entry_once() -> Card:
    return ValidationSmokeCard(
        card_id="real-trade-gate-short-first-entry-v1",
        version="0.1.0",
        symbol="2330",
        trigger_tag="short_first_entry_once",
        side="sell",
        intent_type="enter",
        reason="real trade gate short-capability smoke entry triggered",
    )


def short_first_cover_once() -> Card:
    return ValidationSmokeCard(
        card_id="real-trade-gate-short-first-cover-v1",
        version="0.1.0",
        symbol="2330",
        trigger_tag="short_first_cover_once",
        side="cover",
        intent_type="exit",
        reason="real trade gate short-capability smoke cover triggered",
        require_position_open=True,
    )
