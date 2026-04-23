from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from steamer_card_engine.cli import main
from steamer_card_engine.dashboard import create_app
from steamer_card_engine.observer import (
    build_sim_observer_bundle,
    load_bundle_from_json,
    reset_observer_repository_cache,
    write_sim_observer_bundle_json,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def _twse_us(date: str, clock: str) -> int:
    local = datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=ZoneInfo("Asia/Taipei"))
    return int(local.timestamp() * 1_000_000)


def _build_regular_session_baseline(tmp_path: Path) -> Path:
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    _write_jsonl(
        baseline / "ticks.jsonl",
        [
            {"raw_id": "t1", "raw_event": "data", "symbol": "2330", "time": _twse_us("2026-03-13", "08:59:50"), "price": 950.0, "size": 10},
            {"raw_id": "t2", "raw_event": "data", "symbol": "2330", "time": _twse_us("2026-03-13", "09:00:05"), "price": 951.0, "size": 9},
            {"raw_id": "t3", "raw_event": "data", "symbol": "2330", "time": _twse_us("2026-03-13", "09:01:10"), "price": 952.0, "size": 8},
        ],
    )
    decision_ts = str(_twse_us("2026-03-13", "09:01:10"))
    _write_jsonl(
        baseline / "decisions.jsonl",
        [
            {"stage": "features", "ok": True, "reason": "features:ok", "side": "long", "symbol": "2330", "ts": decision_ts, "metrics": {"bars": 100, "ret_from_open": 0.01}},
            {"stage": "gate", "ok": True, "reason": "gate:ok", "side": "long", "symbol": "2330", "ts": decision_ts, "metrics": {"bars": 100}},
            {"stage": "signal", "ok": True, "reason": "signal:long_trigger", "side": "long", "symbol": "2330", "ts": decision_ts, "metrics": {"bars": 100}},
            {"stage": "entry", "ok": True, "reason": "entry:entered", "side": "long", "symbol": "2330", "ts": decision_ts, "metrics": {"bars": 100}},
        ],
    )
    return baseline


def _emit_sim_bundle(tmp_path: Path) -> Path:
    baseline = _build_regular_session_baseline(tmp_path)
    bundle_dir = tmp_path / "bundle"
    code = main(
        [
            "sim",
            "normalize-baseline",
            "--baseline-dir",
            str(baseline),
            "--output-dir",
            str(bundle_dir),
            "--session-date",
            "2026-03-13",
            "--scenario-id",
            "tw-gap-reclaim.twse.2026-03-13.full-session",
        ]
    )
    assert code == 0
    return bundle_dir


def test_build_sim_observer_bundle_projects_lifecycle_truth(tmp_path: Path) -> None:
    bundle_dir = _emit_sim_bundle(tmp_path)

    observer_bundle = build_sim_observer_bundle(bundle_dir=bundle_dir, session_id="sim-2026-03-13-2330")

    assert observer_bundle.bootstrap.session_id == "sim-2026-03-13-2330"
    assert observer_bundle.bootstrap.symbol == "2330.TW"
    assert observer_bundle.bootstrap.position.side == "long"
    assert observer_bundle.bootstrap.position.quantity == 1
    assert observer_bundle.bootstrap.last_fill is not None
    assert observer_bundle.bootstrap.last_fill.price == 952.0
    assert observer_bundle.bootstrap.open_orders
    assert observer_bundle.bootstrap.open_orders[0].status == "filled"
    assert any(event.event_type == "fill_received" for event in observer_bundle.events)
    assert any(event.event_type == "position_updated" for event in observer_bundle.events)


def test_written_sim_observer_bundle_mounts_via_dashboard(monkeypatch, tmp_path: Path) -> None:
    bundle_dir = _emit_sim_bundle(tmp_path)
    observer_bundle = build_sim_observer_bundle(bundle_dir=bundle_dir, session_id="sim-2026-03-13-2330")
    attachment_path = tmp_path / "observer-sim-attachment.json"
    write_sim_observer_bundle_json(bundle=observer_bundle, output_path=attachment_path)

    reloaded = load_bundle_from_json(attachment_path)
    assert reloaded.bootstrap.position.quantity == 1
    assert reloaded.bootstrap.last_fill is not None
    assert reloaded.bootstrap.last_fill.quantity == 1

    monkeypatch.setenv("STEAMER_OBSERVER_BUNDLE_JSON", str(attachment_path))
    monkeypatch.setenv("STEAMER_OBSERVER_INCLUDE_MOCK", "0")
    reset_observer_repository_cache()

    client = TestClient(create_app())
    sessions = client.get("/api/observer/sessions")
    assert sessions.status_code == 200
    assert sessions.json()["items"] == [
        {
            "session_id": "sim-2026-03-13-2330",
            "engine_id": "steamer-card-engine.sim",
            "symbol": "2330.TW",
            "market_mode": "sim",
            "freshness_state": "fresh",
        }
    ]

    bootstrap = client.get("/api/observer/sessions/sim-2026-03-13-2330/bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()
    assert bootstrap_payload["position"]["side"] == "long"
    assert bootstrap_payload["position"]["quantity"] == 1
    assert bootstrap_payload["last_fill"]["price"] == 952.0
    assert bootstrap_payload["open_orders"][0]["status"] == "filled"

    monkeypatch.delenv("STEAMER_OBSERVER_BUNDLE_JSON", raising=False)
    monkeypatch.delenv("STEAMER_OBSERVER_INCLUDE_MOCK", raising=False)
    reset_observer_repository_cache()
