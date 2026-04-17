from __future__ import annotations

from pathlib import Path

from steamer_card_engine.manifest import load_cards_from_dir, load_deck_manifest
from steamer_card_engine.validation_runtime import (
    default_validation_scenarios,
    load_runtime_cards_from_deck,
    run_validation_scenarios,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_validation_smoke_deck_resolves_to_runtime_card_factories() -> None:
    deck_path = REPO_ROOT / "examples/decks/tw_cash_validation_smoke.toml"
    cards_dir = REPO_ROOT / "examples/cards"

    deck = load_deck_manifest(deck_path)
    cards_by_id = load_cards_from_dir(cards_dir)
    payload, bindings = load_runtime_cards_from_deck(deck_path, cards_dir=cards_dir)

    assert payload["deck_id"] == "tw-cash-validation-smoke"
    assert payload["missing_cards"] == []
    assert payload["live_mode"] is False
    assert deck.policy.live_mode is False

    assert [binding.card_id for binding in bindings] == [
        "smoke-entry-once-v1",
        "smoke-exit-once-v1",
        "smoke-no-trade-guard-v1",
    ]
    assert [binding.entry_module for binding in bindings] == [
        cards_by_id["smoke-entry-once-v1"].entry_module,
        cards_by_id["smoke-exit-once-v1"].entry_module,
        cards_by_id["smoke-no-trade-guard-v1"].entry_module,
    ]
    assert [binding.card.card_id for binding in bindings] == deck.cards
    assert all(cards_by_id[card_id].status == "replay-only" for card_id in deck.cards)


def test_validation_smoke_runtime_bridge_executes_expected_scenarios() -> None:
    deck_path = REPO_ROOT / "examples/decks/tw_cash_validation_smoke.toml"
    cards_dir = REPO_ROOT / "examples/cards"

    _, bindings = load_runtime_cards_from_deck(deck_path, cards_dir=cards_dir)
    result = run_validation_scenarios(bindings, default_validation_scenarios())

    assert result["ok"] is True
    rows = {row["scenario_id"]: row for row in result["scenarios"]}

    assert rows["entry-once"]["intent_ids"] == ["smoke-entry-once-v1:enter:2330"]
    assert rows["exit-blocked-without-position-open"]["intent_ids"] == []
    assert rows["exit-once-after-position-open"]["intent_ids"] == ["smoke-exit-once-v1:exit:2330"]
    assert rows["no-trade-guard"]["intent_count"] == 0
