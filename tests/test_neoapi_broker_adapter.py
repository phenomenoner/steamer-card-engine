from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from steamer_card_engine.adapters.neoapi_broker import NeoApiBrokerAdapter, NeoApiCredentials
from steamer_card_engine.live_execution import build_sell_first_round_trip_plan


class FakeOrder:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class FakeEnum:
    Buy = "Buy"
    Sell = "Sell"
    Common = "Common"
    DayTrade = "DayTrade"
    Stock = "Stock"
    Limit = "Limit"
    IOC = "IOC"


def fake_constants():
    return {
        "Order": FakeOrder,
        "BSAction": FakeEnum,
        "MarketType": FakeEnum,
        "OrderType": FakeEnum,
        "PriceType": FakeEnum,
        "TimeInForce": FakeEnum,
    }


class FakeStock:
    def __init__(self):
        self.orders = []
        self.polls = 0

    def query_symbol_quote(self, account, symbol):
        return SimpleNamespace(
            is_success=True,
            data=SimpleNamespace(status=15, limitdown_price=6.68, limitup_price=8.16),
            message="",
        )

    def place_order(self, account, order):
        self.orders.append(order.kwargs)
        order_no = "S1" if len(self.orders) == 1 else "B1"
        return SimpleNamespace(
            is_success=True,
            message="",
            data=SimpleNamespace(order_no=order_no, status=10, filled_qty=0, stock_no="1314"),
        )

    def get_order_results(self, account):
        self.polls += 1
        rows = []
        if self.orders:
            rows.append(SimpleNamespace(order_no="S1", stock_no="1314", filled_qty=1000, status=50))
        if len(self.orders) >= 2:
            rows.append(SimpleNamespace(order_no="B1", stock_no="1314", filled_qty=1000, status=50))
        return SimpleNamespace(is_success=True, data=rows, message="")


class FakeSdk:
    def __init__(self):
        self.stock = FakeStock()

    def apikey_login(self, *_args):
        return SimpleNamespace(
            is_success=True,
            data=[SimpleNamespace(account_type="stock", account="sample-account")],
            message="",
        )


def test_neoapi_adapter_maps_sell_first_and_buyback_with_fake_sdk(tmp_path: Path) -> None:
    fake_sdk = FakeSdk()
    adapter = NeoApiBrokerAdapter(
        credentials=NeoApiCredentials("A123456789", "k", tmp_path / "c.p12", "p"),
        expected_account_no="sample-account",
        sdk_factory=lambda: fake_sdk,
        constants_factory=fake_constants,
    )
    receipt = adapter.execute_round_trip(build_sell_first_round_trip_plan(symbol="1314", quantity=1000))
    assert receipt["status"] == "round-trip-closed"
    assert fake_sdk.stock.orders[0]["buy_sell"] == "Sell"
    assert fake_sdk.stock.orders[0]["order_type"] == "DayTrade"
    assert fake_sdk.stock.orders[0]["time_in_force"] == "IOC"
    assert fake_sdk.stock.orders[1]["buy_sell"] == "Buy"
    assert fake_sdk.stock.orders[1]["order_type"] == "Stock"
    assert fake_sdk.stock.orders[1]["quantity"] == 1000


def test_neoapi_adapter_refuses_account_mismatch(tmp_path: Path) -> None:
    fake_sdk = FakeSdk()
    adapter = NeoApiBrokerAdapter(
        credentials=NeoApiCredentials("A123456789", "k", tmp_path / "c.p12", "p"),
        expected_account_no="different-account",
        sdk_factory=lambda: fake_sdk,
        constants_factory=fake_constants,
    )
    receipt = adapter.execute_round_trip(build_sell_first_round_trip_plan(symbol="1314", quantity=1000))
    assert receipt["status"] == "account-mismatch-refused"
    assert fake_sdk.stock.orders == []
