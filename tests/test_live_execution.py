from __future__ import annotations

from datetime import date
from pathlib import Path

from steamer_card_engine.live_execution import (
    DryRunRoundTripAdapter,
    FirstLiveRiskGuard,
    LiveExecutionPolicy,
    RoundTripLedger,
    build_sell_first_round_trip_plan,
)


def test_first_live_risk_guard_blocks_non_allowlist_and_oversize(tmp_path: Path) -> None:
    guard = FirstLiveRiskGuard(
        policy=LiveExecutionPolicy(symbol_allowlist=frozenset({"1314"}), max_quantity=1000),
        ledger=RoundTripLedger(tmp_path / "ledger.json"),
    )
    result = guard.evaluate(symbol="2330", quantity=2000, today=date(2026, 5, 4))
    codes = {row["code"] for row in result.blockers}
    assert result.allowed is False
    assert "symbol-not-allowlisted" in codes
    assert "quantity-exceeds-policy" in codes


def test_first_live_risk_guard_blocks_second_roundtrip(tmp_path: Path) -> None:
    ledger = RoundTripLedger(tmp_path / "ledger.json")
    ledger.record_closed(day=date(2026, 5, 4), symbol="1314", plan_id="p1", receipt_id="r1")
    guard = FirstLiveRiskGuard(
        policy=LiveExecutionPolicy(symbol_allowlist=frozenset({"1314"}), max_round_trips_per_day=1),
        ledger=ledger,
    )
    result = guard.evaluate(symbol="1314", quantity=1000, today=date(2026, 5, 4))
    assert result.allowed is False
    assert {row["code"] for row in result.blockers} == {"roundtrip-limit-reached"}


def test_sell_first_plan_maps_entry_and_buyback() -> None:
    plan = build_sell_first_round_trip_plan(symbol="1314", quantity=1000)
    assert plan.entry.side == "sell"
    assert plan.exit.side == "buy"
    assert plan.broker_mapping["entry"]["order_type"] == "DayTrade"
    assert plan.broker_mapping["entry"]["time_in_force"] == "IOC"
    assert plan.broker_mapping["exit"]["order_type"] == "Stock"


def test_dry_run_adapter_dispatch_suppressed() -> None:
    plan = build_sell_first_round_trip_plan(symbol="1314", quantity=1000)
    receipt = DryRunRoundTripAdapter().execute_round_trip(plan)
    assert receipt["status"] == "dry-run-closed"
    assert receipt["dispatch_suppressed"] is True
    assert receipt["entry_receipt"]["status"] == "dry-run-accepted"
    assert receipt["exit_receipt"]["status"] == "dry-run-accepted"
