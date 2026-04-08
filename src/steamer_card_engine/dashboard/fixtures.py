from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SCENARIO_DATE_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _comparison_family(name: str) -> str:
    if name.startswith("manual-live-paired-"):
        return "manual-live-paired"
    if name.startswith("replay-sim_"):
        return "replay-sim"
    if name.startswith("prep-"):
        return "prep"
    if name.startswith("phase3_"):
        return "phase3"
    return "other"


def _comparison_priority(name: str) -> int:
    family = _comparison_family(name)
    return {
        "manual-live-paired": 40,
        "replay-sim": 30,
        "prep": 20,
        "phase3": 10,
        "other": 0,
    }[family]


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
    compare_status: str
    compare_version: str
    comparison_family: str


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _scenario_date(manifest: dict[str, Any]) -> str | None:
    scenario_id = str(manifest.get("scenario", {}).get("scenario_id", ""))
    match = SCENARIO_DATE_PATTERN.search(scenario_id)
    if match is None:
        return None
    return match.group(1)


def _resolve_bundle_dir(
    manifest_entry: dict[str, Any],
    runs_root: Path,
    fallback_date: str | None,
) -> Path | None:
    bundle_dir = manifest_entry.get("bundle_dir")
    if isinstance(bundle_dir, str) and bundle_dir:
        bundle_path = Path(bundle_dir)
        if bundle_path.exists():
            return bundle_path

    lane = manifest_entry.get("lane")
    run_id = manifest_entry.get("run_id")
    if not isinstance(lane, str) or not isinstance(run_id, str) or fallback_date is None:
        return None

    fallback_path = runs_root / lane / fallback_date / run_id
    if fallback_path.exists():
        return fallback_path
    return None


def _bundle_date(path: Path) -> str | None:
    if DATE_DIR_PATTERN.fullmatch(path.parent.name):
        return path.parent.name
    return None


def discover_fixture_days(root: Path | None = None) -> list[FixtureDay]:
    base_root = root or repo_root()
    comparisons_root = base_root / "comparisons"
    runs_root = base_root / "runs"

    discovered: dict[str, tuple[tuple[bool, int, str], FixtureDay]] = {}

    for comparison_dir in sorted(comparisons_root.iterdir()):
        if not comparison_dir.is_dir():
            continue

        compare_manifest = comparison_dir / "compare-manifest.json"
        diff = comparison_dir / "diff.json"
        summary = comparison_dir / "summary.md"
        if not compare_manifest.exists() or not diff.exists() or not summary.exists():
            continue

        manifest = _load_json(compare_manifest)
        baseline_manifest = manifest.get("baseline", {})
        candidate_manifest = manifest.get("candidate", {})
        if baseline_manifest.get("lane") != "baseline-bot":
            continue
        if candidate_manifest.get("lane") != "steamer-card-engine":
            continue

        scenario_date = _scenario_date(manifest)
        baseline_dir = _resolve_bundle_dir(baseline_manifest, runs_root, scenario_date)
        candidate_dir = _resolve_bundle_dir(candidate_manifest, runs_root, scenario_date)
        if baseline_dir is None or candidate_dir is None:
            continue

        baseline_date = _bundle_date(baseline_dir)
        candidate_date = _bundle_date(candidate_dir)
        if baseline_date is None or candidate_date is None or baseline_date != candidate_date:
            continue

        date = baseline_date
        fixture = FixtureDay(
            date=date,
            comparison_dir=comparison_dir,
            baseline_dir=baseline_dir,
            candidate_dir=candidate_dir,
            baseline_run_id=str(baseline_manifest["run_id"]),
            candidate_run_id=str(candidate_manifest["run_id"]),
            compare_manifest=compare_manifest,
            diff=diff,
            summary=summary,
            compare_status=str(manifest.get("status", "unknown")),
            compare_version=str(manifest.get("compare_version", "unknown")),
            comparison_family=_comparison_family(comparison_dir.name),
        )
        selection_key = (
            fixture.compare_status == "pass",
            _comparison_priority(comparison_dir.name),
            comparison_dir.name,
        )
        existing = discovered.get(date)
        if existing is None or selection_key > existing[0]:
            discovered[date] = (selection_key, fixture)

    return [discovered[date][1] for date in sorted(discovered.keys(), reverse=True)]
