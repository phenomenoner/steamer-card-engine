from __future__ import annotations

from steamer_card_engine.cards.base import MarketContext
from steamer_card_engine.cards.validation_smoke import (
    entry_once,
    exit_once,
    no_trade_guard,
    short_first_cover_once,
    short_first_entry_once,
)


def test_validation_smoke_entry_once_emits_buy_intent() -> None:
    card = entry_once()

    intents = card.on_event(MarketContext(symbol="2330", last_price=100.0, tags=("entry_once",)))

    assert len(intents) == 1
    intent = intents[0]
    assert intent.card_id == "smoke-entry-once-v1"
    assert intent.side == "buy"
    assert intent.intent_type == "enter"
    assert intent.reason == "validation smoke entry triggered"


def test_validation_smoke_entry_once_stays_silent_without_trigger() -> None:
    card = entry_once()

    intents = card.on_event(MarketContext(symbol="2330", last_price=100.0, tags=()))

    assert intents == []


def test_validation_smoke_exit_once_requires_open_position_tag() -> None:
    card = exit_once()

    blocked = card.on_event(MarketContext(symbol="2330", last_price=100.0, tags=("exit_once",)))
    allowed = card.on_event(
        MarketContext(symbol="2330", last_price=100.0, tags=("exit_once", "position_open"))
    )

    assert blocked == []
    assert len(allowed) == 1
    assert allowed[0].side == "exit"
    assert allowed[0].intent_type == "exit"


def test_validation_smoke_no_trade_guard_never_emits_intent() -> None:
    card = no_trade_guard()

    intents = card.on_event(
        MarketContext(symbol="2317", last_price=100.0, tags=("entry_once", "position_open"))
    )

    assert intents == []


def test_real_trade_gate_short_first_entry_emits_sell_intent() -> None:
    card = short_first_entry_once()

    intents = card.on_event(
        MarketContext(symbol="2330", last_price=100.0, tags=("short_first_entry_once",))
    )

    assert len(intents) == 1
    intent = intents[0]
    assert intent.card_id == "real-trade-gate-short-first-entry-v1"
    assert intent.side == "sell"
    assert intent.intent_type == "enter"
    assert intent.reason == "real trade gate short-capability smoke entry triggered"


def test_real_trade_gate_short_first_cover_requires_position_open() -> None:
    card = short_first_cover_once()

    blocked = card.on_event(MarketContext(symbol="2330", last_price=100.0, tags=("short_first_cover_once",)))
    allowed = card.on_event(
        MarketContext(symbol="2330", last_price=100.0, tags=("short_first_cover_once", "position_open"))
    )

    assert blocked == []
    assert len(allowed) == 1
    assert allowed[0].side == "cover"
    assert allowed[0].intent_type == "exit"
