from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class RuntimeRunRoot:
    """A discovered runtime run root plus the adapter that recognized it."""

    path: Path
    date: str
    adapter_id: str
    source_kind: str
    lane: str | None = None


class RuntimeSourceAdapter(Protocol):
    adapter_id: str
    source_kind: str

    def discover_dates(self) -> set[str]: ...

    def discover_run_roots(self, date: str) -> list[RuntimeRunRoot]: ...


def parse_runtime_date(value: str) -> str:
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return text.replace("-", "")
    return text


def dashed_runtime_date(date: str) -> str:
    compact = parse_runtime_date(date)
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


class LocalRunsAdapter:
    adapter_id = "local-runs"
    source_kind = "runtime-local-runs-layout"

    def __init__(self, root: Path) -> None:
        self.root = root

    def _lane_roots(self) -> list[tuple[str, Path]]:
        return [
            ("steamer-card-engine", self.root / "runs" / "steamer-card-engine"),
            ("baseline-bot", self.root / "runs" / "baseline-bot"),
        ]

    def discover_dates(self) -> set[str]:
        dates: set[str] = set()
        for _, lane_root in self._lane_roots():
            if not lane_root.exists():
                continue
            for item in lane_root.iterdir():
                if item.is_dir() and len(item.name) == 10 and item.name[4] == "-" and item.name[7] == "-":
                    dates.add(item.name.replace("-", ""))
        return dates

    def discover_run_roots(self, date: str) -> list[RuntimeRunRoot]:
        dashed = dashed_runtime_date(date)
        roots: list[RuntimeRunRoot] = []
        for lane, lane_root in self._lane_roots():
            date_root = lane_root / dashed
            if not date_root.exists():
                continue
            roots.extend(
                RuntimeRunRoot(item, parse_runtime_date(date), self.adapter_id, self.source_kind, lane=lane)
                for item in date_root.iterdir()
                if item.is_dir() and ("live-sim" in item.name or "neoapi" in item.name)
            )
        return roots


class AwsLiveSimAdapter:
    adapter_id = "aws-live-sim"
    source_kind = "runtime-aws-live-sim-layout"

    def __init__(self, root: Path) -> None:
        self.root = root

    def discover_dates(self) -> set[str]:
        if not self.root.exists():
            return set()
        return {item.name for item in self.root.iterdir() if item.is_dir() and len(item.name) == 8 and item.name.isdigit()}

    def _looks_like_run_root(self, item: Path, compact_date: str) -> bool:
        if not item.is_dir():
            return False
        return any(source.exists() for source in runtime_tick_sources(item, compact_date)) or (item / "data" / compact_date).exists()

    def discover_run_roots(self, date: str) -> list[RuntimeRunRoot]:
        compact = parse_runtime_date(date)
        date_root = self.root / compact
        if not date_root.exists():
            return []
        return [
            RuntimeRunRoot(item, compact, self.adapter_id, self.source_kind, lane="aws-live-sim")
            for item in date_root.iterdir()
            if self._looks_like_run_root(item, compact)
        ]


def configured_runtime_root() -> Path | None:
    raw = os.getenv("STEAMER_DASHBOARD_RUNTIME_ROOT")
    return Path(raw) if raw else None


def runtime_source_adapters(root: Path) -> list[RuntimeSourceAdapter]:
    roots = [root]
    configured = configured_runtime_root()
    if configured is not None and configured not in roots:
        roots.append(configured)
    adapters: list[RuntimeSourceAdapter] = []
    for item in roots:
        adapters.append(LocalRunsAdapter(item))
        adapters.append(AwsLiveSimAdapter(item))
    return adapters


def discover_runtime_dates(root: Path) -> list[str]:
    dates: set[str] = set()
    for adapter in runtime_source_adapters(root):
        dates.update(adapter.discover_dates())
    return sorted(dates, reverse=True)


def discover_runtime_run_roots(root: Path, date: str) -> list[RuntimeRunRoot]:
    discovered: dict[str, RuntimeRunRoot] = {}
    for adapter in runtime_source_adapters(root):
        for run_root in adapter.discover_run_roots(date):
            discovered[str(run_root.path)] = run_root
    return sorted(discovered.values(), key=lambda item: (item.adapter_id, item.path.name), reverse=True)


def runtime_tick_sources(run_root: Path, date: str) -> list[Path]:
    compact = parse_runtime_date(date)
    return [
        run_root / "data" / compact / "ticks.jsonl",
        run_root / "ticks.jsonl",
        run_root / "event-log.jsonl",
    ]
