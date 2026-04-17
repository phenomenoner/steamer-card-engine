from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from steamer_card_engine.cards.base import Card, MarketContext
from steamer_card_engine.manifest import load_cards_from_dir, load_deck_manifest
from steamer_card_engine.models import Intent


@dataclass(slots=True)
class RuntimeCardBinding:
    card_id: str
    entry_module: str
    card: Card


@dataclass(slots=True)
class ValidationScenario:
    scenario_id: str
    symbol: str
    last_price: float
    tags: tuple[str, ...]
    expected_intent_ids: tuple[str, ...]
    expected_card_ids: tuple[str, ...]
    expected_intent_count: int


def resolve_card_factory(entry_module: str) -> Callable[[], Card]:
    module_name, sep, factory_name = entry_module.partition(":")
    if not sep or not module_name or not factory_name:
        raise ValueError(f"invalid entry_module, expected '<module>:<factory>': {entry_module}")

    module = import_module(module_name)
    factory = getattr(module, factory_name, None)
    if factory is None or not callable(factory):
        raise ValueError(f"entry_module factory is not callable: {entry_module}")
    return factory


def load_runtime_cards_from_deck(deck_path: str | Path, *, cards_dir: str | Path) -> tuple[dict[str, Any], list[RuntimeCardBinding]]:
    deck = load_deck_manifest(deck_path)
    cards_by_id = load_cards_from_dir(cards_dir)

    bindings: list[RuntimeCardBinding] = []
    missing_cards: list[str] = []
    for card_id in deck.cards:
        manifest = cards_by_id.get(card_id)
        if manifest is None:
            missing_cards.append(card_id)
            continue
        factory = resolve_card_factory(manifest.entry_module)
        bindings.append(
            RuntimeCardBinding(
                card_id=manifest.card_id,
                entry_module=manifest.entry_module,
                card=factory(),
            )
        )

    payload = {
        "deck_id": deck.deck_id,
        "deck_path": str(Path(deck_path).resolve()),
        "cards_dir": str(Path(cards_dir).resolve()),
        "card_ids": list(deck.cards),
        "missing_cards": missing_cards,
        "live_mode": deck.policy.live_mode,
    }
    return payload, bindings


def run_validation_scenarios(bindings: list[RuntimeCardBinding], scenarios: list[ValidationScenario]) -> dict[str, Any]:
    scenario_rows: list[dict[str, Any]] = []
    all_ok = True

    for scenario in scenarios:
        context = MarketContext(symbol=scenario.symbol, last_price=scenario.last_price, tags=scenario.tags)
        intents: list[Intent] = []
        for binding in bindings:
            intents.extend(binding.card.on_event(context))

        intent_ids = [intent.intent_id for intent in intents]
        card_ids = [intent.card_id for intent in intents]
        ok = (
            len(intents) == scenario.expected_intent_count
            and tuple(intent_ids) == scenario.expected_intent_ids
            and tuple(card_ids) == scenario.expected_card_ids
        )
        all_ok = all_ok and ok
        scenario_rows.append(
            {
                "scenario_id": scenario.scenario_id,
                "symbol": scenario.symbol,
                "tags": list(scenario.tags),
                "intent_count": len(intents),
                "intent_ids": intent_ids,
                "card_ids": card_ids,
                "ok": ok,
                "expected": {
                    "intent_count": scenario.expected_intent_count,
                    "intent_ids": list(scenario.expected_intent_ids),
                    "card_ids": list(scenario.expected_card_ids),
                },
            }
        )

    return {
        "ok": all_ok,
        "scenarios": scenario_rows,
    }


def default_validation_scenarios() -> list[ValidationScenario]:
    return [
        ValidationScenario(
            scenario_id="entry-once",
            symbol="2330",
            last_price=100.0,
            tags=("entry_once",),
            expected_intent_ids=("smoke-entry-once-v1:enter:2330",),
            expected_card_ids=("smoke-entry-once-v1",),
            expected_intent_count=1,
        ),
        ValidationScenario(
            scenario_id="exit-blocked-without-position-open",
            symbol="2330",
            last_price=100.0,
            tags=("exit_once",),
            expected_intent_ids=(),
            expected_card_ids=(),
            expected_intent_count=0,
        ),
        ValidationScenario(
            scenario_id="exit-once-after-position-open",
            symbol="2330",
            last_price=100.0,
            tags=("exit_once", "position_open"),
            expected_intent_ids=("smoke-exit-once-v1:exit:2330",),
            expected_card_ids=("smoke-exit-once-v1",),
            expected_intent_count=1,
        ),
        ValidationScenario(
            scenario_id="no-trade-guard",
            symbol="2317",
            last_price=100.0,
            tags=("no_trade",),
            expected_intent_ids=(),
            expected_card_ids=(),
            expected_intent_count=0,
        ),
    ]
