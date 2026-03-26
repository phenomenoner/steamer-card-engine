from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


SCHEMA_VERSION_V0 = "strategy_catalog_metadata.v0"


class StrategyCatalogValidationError(ValueError):
    def __init__(self, path: Path, errors: list[str]) -> None:
        self.path = path
        self.errors = errors
        joined = "\n".join(f"- {error}" for error in errors)
        super().__init__(f"Invalid strategy catalog metadata: {path}\n{joined}")


@dataclass(frozen=True, slots=True)
class StrategyCatalogEntry:
    card_id: str
    display_name: str | None = None
    aliases: list[str] = field(default_factory=list)
    default_priority: int | None = None
    market_regimes: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)

    def normalized_market_regimes(self) -> set[str]:
        return {tag.strip().lower() for tag in self.market_regimes if tag.strip()}


@dataclass(frozen=True, slots=True)
class StrategyCatalog:
    schema_version: str
    strategies: list[StrategyCatalogEntry]
    catalog_id: str | None = None
    updated_at: str | None = None
    notes: str | None = None


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as file:
            data = tomllib.load(file)
    except FileNotFoundError as exc:
        raise StrategyCatalogValidationError(path, ["file not found"]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise StrategyCatalogValidationError(path, [f"toml parse error: {exc}"]) from exc

    if not isinstance(data, dict):
        raise StrategyCatalogValidationError(path, ["top-level TOML object must be a table"])
    return data


def _require_str(payload: dict[str, Any], key: str, errors: list[str]) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"`{key}` must be a non-empty string")
        return ""
    return value.strip()


def _optional_str(payload: dict[str, Any], key: str, errors: list[str]) -> str | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    errors.append(f"`{key}` must be a non-empty string when set")
    return None


def _optional_int(payload: dict[str, Any], key: str, errors: list[str]) -> int | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if isinstance(value, bool):
        errors.append(f"`{key}` must be an integer when set")
        return None
    if isinstance(value, int):
        return value
    errors.append(f"`{key}` must be an integer when set")
    return None


def _optional_str_list(payload: dict[str, Any], key: str, errors: list[str]) -> list[str]:
    if key not in payload:
        return []
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"`{key}` must be an array of non-empty strings when set")
        return []
    cleaned = [item.strip() for item in value]
    if len(set(cleaned)) != len(cleaned):
        errors.append(f"`{key}` must not contain duplicates")
    return cleaned


def load_strategy_catalog(path: str | Path) -> StrategyCatalog:
    resolved = Path(path)
    payload = _load_toml(resolved)
    errors: list[str] = []

    schema_version = _require_str(payload, "schema_version", errors)
    if schema_version and schema_version != SCHEMA_VERSION_V0:
        errors.append(
            f"`schema_version` must be '{SCHEMA_VERSION_V0}' (got '{schema_version}')"
        )

    catalog_id = _optional_str(payload, "catalog_id", errors)
    updated_at = _optional_str(payload, "updated_at", errors)
    notes = _optional_str(payload, "notes", errors)

    raw_strategies = payload.get("strategies")
    if raw_strategies is None:
        errors.append("`strategies` must be set (use [[strategies]] array-of-tables)")
        raw_strategies = []
    if not isinstance(raw_strategies, list):
        errors.append("`strategies` must be an array-of-tables")
        raw_strategies = []

    entries: list[StrategyCatalogEntry] = []
    seen_card_ids: set[str] = set()

    for index, raw in enumerate(raw_strategies):
        if not isinstance(raw, dict):
            errors.append(f"strategies[{index}] must be a table")
            continue

        entry_errors: list[str] = []
        card_id = _require_str(raw, "card_id", entry_errors)
        display_name = _optional_str(raw, "display_name", entry_errors)
        aliases = _optional_str_list(raw, "aliases", entry_errors)
        default_priority = _optional_int(raw, "default_priority", entry_errors)
        market_regimes = _optional_str_list(raw, "market_regimes", entry_errors)
        required_evidence = _optional_str_list(raw, "required_evidence", entry_errors)
        required_tools = _optional_str_list(raw, "required_tools", entry_errors)

        if card_id:
            if card_id in seen_card_ids:
                entry_errors.append(f"duplicate card_id: {card_id}")
            seen_card_ids.add(card_id)

        if entry_errors:
            prefixed = [f"strategies[{index}]: {issue}" for issue in entry_errors]
            errors.extend(prefixed)
            continue

        entries.append(
            StrategyCatalogEntry(
                card_id=card_id,
                display_name=display_name,
                aliases=aliases,
                default_priority=default_priority,
                market_regimes=market_regimes,
                required_evidence=required_evidence,
                required_tools=required_tools,
            )
        )

    if errors:
        raise StrategyCatalogValidationError(resolved, errors)

    return StrategyCatalog(
        schema_version=schema_version,
        catalog_id=catalog_id,
        updated_at=updated_at,
        notes=notes,
        strategies=entries,
    )


def summarize_strategy_catalog(catalog: StrategyCatalog) -> dict[str, Any]:
    regimes: set[str] = set()
    for entry in catalog.strategies:
        regimes.update(entry.normalized_market_regimes())

    return {
        "schema_version": catalog.schema_version,
        "catalog_id": catalog.catalog_id,
        "updated_at": catalog.updated_at,
        "notes": catalog.notes,
        "strategies_total": len(catalog.strategies),
        "market_regimes": sorted(regimes),
    }


def query_strategies_by_regime(
    catalog: StrategyCatalog,
    regimes: list[str],
) -> list[StrategyCatalogEntry]:
    wanted = {regime.strip().lower() for regime in regimes if regime.strip()}
    if not wanted:
        return []

    matches = [
        entry
        for entry in catalog.strategies
        if entry.normalized_market_regimes() & wanted
    ]

    return sorted(
        matches,
        key=lambda entry: (
            -(entry.default_priority or 0),
            entry.card_id,
        ),
    )
