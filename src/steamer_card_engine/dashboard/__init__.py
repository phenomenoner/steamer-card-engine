from __future__ import annotations

from typing import Any

__all__ = ["DashboardDataError", "build_day_bundle", "create_app", "list_fixture_dates"]


def create_app(*args: Any, **kwargs: Any):
    from .api import create_app as _create_app

    return _create_app(*args, **kwargs)


def build_day_bundle(*args: Any, **kwargs: Any):
    from .aggregator import build_day_bundle as _build_day_bundle

    return _build_day_bundle(*args, **kwargs)


def list_fixture_dates(*args: Any, **kwargs: Any):
    from .aggregator import list_fixture_dates as _list_fixture_dates

    return _list_fixture_dates(*args, **kwargs)


def __getattr__(name: str):
    if name == "DashboardDataError":
        from .aggregator import DashboardDataError

        return DashboardDataError
    raise AttributeError(name)
