from __future__ import annotations

import json

from steamer_card_engine.cli import main


def test_cli_validate_card_success(capsys) -> None:
    code = main(["author", "validate-card", "examples/cards/gap_reclaim.toml"])

    captured = capsys.readouterr()
    assert code == 0
    assert "OK: card manifest is valid" in captured.out


def test_cli_inspect_deck_json(capsys) -> None:
    code = main(
        [
            "author",
            "inspect-deck",
            "examples/decks/tw_cash_intraday.toml",
            "--cards-dir",
            "examples/cards",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert code == 0
    assert payload["deck_id"] == "tw-cash-main"
    assert "gap-reclaim-v1" in payload["enabled_cards"]
    assert "2330" in payload["merged_symbol_scope"]


def test_cli_validate_auth_failure(capsys) -> None:
    code = main(["auth", "validate-profile", "tests/fixtures/bad_auth_missing_key.toml"])

    captured = capsys.readouterr()
    assert code == 2
    assert "Validation failed for auth_profile manifest" in captured.out
