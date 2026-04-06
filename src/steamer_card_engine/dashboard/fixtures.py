from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re


COMPARISON_DIR_PATTERN = re.compile(
    r"^replay-sim_tw-paper-sim-twse-(\d{4}-\d{2}-\d{2})-full-session_"
    r"baseline_.+__replay-sim_tw-paper-sim-twse-\1-full-session_candidate_.+$"
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FixtureDay:
    date: str
    comparison_dir: Path
    baseline_dir: Path
    candidate_dir: Path
    baseline_run_id: str
    candidate_run_id: str
    compare_manifest: Path
    diff: Path
    summary: Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def discover_fixture_days(root: Path | None = None) -> list[FixtureDay]:
    base_root = root or repo_root()
    comparisons_root = base_root / "comparisons"
    runs_root = base_root / "runs"

    discovered: dict[str, FixtureDay] = {}

    for comparison_dir in sorted(comparisons_root.iterdir()):
        if not comparison_dir.is_dir():
            continue
        match = COMPARISON_DIR_PATTERN.match(comparison_dir.name)
        if not match:
            continue

        date = match.group(1)
        compare_manifest = comparison_dir / "compare-manifest.json"
        diff = comparison_dir / "diff.json"
        summary = comparison_dir / "summary.md"
        if not compare_manifest.exists() or not diff.exists() or not summary.exists():
            continue

        manifest = _load_json(compare_manifest)
        baseline_run_id = manifest["baseline"]["run_id"]
        candidate_run_id = manifest["candidate"]["run_id"]
        baseline_dir = runs_root / "baseline-bot" / date / baseline_run_id
        candidate_dir = runs_root / "steamer-card-engine" / date / candidate_run_id
        if not baseline_dir.exists() or not candidate_dir.exists():
            continue

        fixture = FixtureDay(
            date=date,
            comparison_dir=comparison_dir,
            baseline_dir=baseline_dir,
            candidate_dir=candidate_dir,
            baseline_run_id=baseline_run_id,
            candidate_run_id=candidate_run_id,
            compare_manifest=compare_manifest,
            diff=diff,
            summary=summary,
        )
        existing = discovered.get(date)
        if existing is None or comparison_dir.name > existing.comparison_dir.name:
            discovered[date] = fixture

    return [discovered[date] for date in sorted(discovered.keys(), reverse=True)]
