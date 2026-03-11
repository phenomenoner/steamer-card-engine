from __future__ import annotations

from pathlib import Path

import pytest

from steamer_card_engine.manifest import (
    ManifestValidationError,
    load_auth_profile,
    load_card_manifest,
    load_deck_manifest,
    load_global_config,
    summarize_deck_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_example_manifests_validate() -> None:
    auth = load_auth_profile(REPO_ROOT / "examples/profiles/tw_cash_agent_assist.toml")
    card = load_card_manifest(REPO_ROOT / "examples/cards/gap_reclaim.toml")
    deck = load_deck_manifest(REPO_ROOT / "examples/decks/tw_cash_intraday.toml")
    global_config = load_global_config(REPO_ROOT / "examples/config/global.toml")

    assert auth.mode == "account_api_key_cert"
    assert card.card_id == "gap-reclaim-v1"
    assert deck.cards == ["gap-reclaim-v1"]
    assert global_config.risk.emergency_stop is not None


def test_auth_supports_both_login_modes() -> None:
    mode_a = load_auth_profile(REPO_ROOT / "examples/profiles/tw_cash_password_auth.toml")
    mode_b = load_auth_profile(REPO_ROOT / "examples/profiles/tw_cash_agent_assist.toml")

    assert mode_a.mode == "account_password_cert"
    assert mode_a.trade_enabled is True
    assert mode_b.mode == "account_api_key_cert"
    assert mode_b.trade_enabled is False


def test_deck_summary_merges_symbol_pool_when_allowed() -> None:
    deck = load_deck_manifest(REPO_ROOT / "examples/decks/tw_cash_intraday.toml")
    card = load_card_manifest(REPO_ROOT / "examples/cards/gap_reclaim.toml")

    summary = summarize_deck_manifest(deck, cards_by_id={card.card_id: card})

    assert "2317" in summary["merged_symbol_scope"]
    assert "3017" in summary["merged_symbol_scope"]
    assert "indicator.macd.12_26_9" in summary["merged_feature_requirements"]


def test_invalid_auth_profile_missing_secret_pair_raises() -> None:
    bad = REPO_ROOT / "tests/fixtures/bad_auth_missing_key.toml"

    with pytest.raises(ManifestValidationError):
        load_auth_profile(bad)
