from __future__ import annotations

from collections import defaultdict
import os
from pathlib import Path
from typing import Any

from .fixtures import DATE_DIR_PATTERN, discover_fixture_days, repo_root

def _count_runtime_runs(runs_root: Path) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(dict)
    if not runs_root.exists():
        return {}
    for lane_dir in sorted(runs_root.iterdir()):
        if not lane_dir.is_dir():
            continue
        lane = lane_dir.name
        for date_dir in sorted(lane_dir.iterdir()):
            if not date_dir.is_dir() or not DATE_DIR_PATTERN.fullmatch(date_dir.name):
                continue
            runtime_runs = [
                run_dir
                for run_dir in date_dir.iterdir()
                if run_dir.is_dir() and ("live-sim" in run_dir.name or "neoapi" in run_dir.name)
            ]
            if runtime_runs:
                counts[date_dir.name][lane] = len(runtime_runs)
    return dict(counts)


def _list_watchlist_dates(root: Path) -> set[str]:
    dates: set[str] = set()
    candidates = [root / "staging" / "steamer" / "watchlists"]
    configured_watchlist_root = os.getenv("STEAMER_DASHBOARD_WATCHLIST_ROOT")
    if configured_watchlist_root:
        candidates.append(Path(configured_watchlist_root))
    for watchlist_root in candidates:
        if not watchlist_root.exists():
            continue
        for item in watchlist_root.iterdir():
            if item.is_dir() and DATE_DIR_PATTERN.fullmatch(item.name):
                dates.add(item.name)
    return dates


def _list_s3_runtime_dates(root: Path) -> dict[str, dict[str, bool]]:
    """Return S3 archive hints from a local optional cache.

    Live AWS listing stays outside request handling. Operators may materialize this cache
    from S3 readback; absent cache is a truthful unknown, not a blocker.
    """
    cache = root / ".state" / "steamer" / "runtime-s3-index.json"
    if not cache.exists():
        return {}
    try:
        import json

        payload = json.loads(cache.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: dict[str, dict[str, bool]] = {}
    for item in payload.get("dates", []):
        if not isinstance(item, dict):
            continue
        raw_date = str(item.get("date") or "").strip()
        if len(raw_date) == 8 and raw_date.isdigit():
            date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        else:
            date = raw_date
        if not DATE_DIR_PATTERN.fullmatch(date):
            continue
        out[date] = {
            "s3_archive_present": bool(item.get("s3_archive_present")),
            "s3_manifest_present": bool(item.get("s3_manifest_present")),
        }
    return out


def build_runtime_dates_index(root: Path | None = None) -> dict[str, Any]:
    base_root = root or repo_root()
    db_dates: dict[str, dict[str, Any]] = {}
    store_path = os.getenv("STEAMER_DASHBOARD_RUNTIME_DB")
    if store_path:
        from .runtime_store import build_runtime_dates_catalog_from_store

        catalog = build_runtime_dates_catalog_from_store(store_path)
        if catalog is not None:
            db_dates = {item["date"]: item for item in catalog["dates"]}
    local_counts = _count_runtime_runs(base_root / "runs")
    fixture_days = discover_fixture_days(base_root)
    fixture_by_date = {item.date: item for item in fixture_days}
    s3_by_date = _list_s3_runtime_dates(base_root)
    watchlist_dates = _list_watchlist_dates(base_root)

    all_dates = sorted(set(local_counts) | set(s3_by_date) | set(fixture_by_date) | watchlist_dates | set(db_dates), reverse=True)
    dates: list[dict[str, Any]] = []
    for date in all_dates:
        lanes = local_counts.get(date, {})
        db_state = db_dates.get(date, {})
        local_run_count = max(sum(lanes.values()), int(db_state.get("local_run_count") or 0))
        s3_state = s3_by_date.get(date, {})
        fixture = fixture_by_date.get(date)
        dates.append(
            {
                "date": date,
                "local_run_count": local_run_count,
                "lanes": lanes,
                "s3_archive_present": bool(s3_state.get("s3_archive_present")),
                "s3_manifest_present": bool(s3_state.get("s3_manifest_present")),
                "watchlist_present": date in watchlist_dates,
                "db_tick_count": int(db_state.get("db_tick_count") or 0),
                "fixture_compare_present": fixture is not None,
                "fixture_compare_status": fixture.compare_status if fixture else None,
                "comparison_family": fixture.comparison_family if fixture else None,
                "preferred": local_run_count > 0 or int(db_state.get("db_tick_count") or 0) > 0 or bool(s3_state.get("s3_archive_present")) or date in watchlist_dates,
            }
        )

    return {
        "source_kind": "runtime-store-sqlite-catalog+local-runs+s3-runtime-archive-cache+fixture-compare-index" if db_dates else "local-runs+s3-runtime-archive-cache+fixture-compare-index",
        "archive_bucket_configured": bool(os.getenv("STEAMER_DASHBOARD_RUNTIME_BUCKET")),
        "date_count": len(dates),
        "runtime_date_count": sum(1 for item in dates if item["local_run_count"] > 0 or item["s3_archive_present"] or item["watchlist_present"]),
        "fixture_dates": [item.date for item in fixture_days],
        "dates": dates,
        "notes": [
            "S3 archive flags are populated from optional local cache .state/steamer/runtime-s3-index.json; local run counts are authoritative for this checkout when runs are deployed.",
            "Watchlist dates are included as runtime collection evidence when full run bundles are not present on the release host.",
            "Fixture compare dates are retained as compare provenance, not the primary runtime date index.",
        ],
    }
