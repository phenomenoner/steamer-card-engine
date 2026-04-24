from steamer_card_engine.runtime.components import MarketDataHub


def test_market_data_hub_stats_are_aggregate_only() -> None:
    hub = MarketDataHub(
        subscribed_symbols={"<SYMBOL_A>", "<SYMBOL_B>"},
        subscriber_count=3,
        event_count=42,
        last_event_at_utc="2026-04-24T00:00:00.000Z",
        connection_state="replaying",
        error_count=1,
        last_error_class="parse_error",
    )

    stats = hub.stats()

    assert stats.schema_version == "market-data-hub-stats/v1"
    assert stats.subscription_count == 2
    assert stats.subscriber_count == 3
    assert stats.event_count == 42
    assert stats.last_event_at_utc == "2026-04-24T00:00:00.000Z"
    assert stats.connection_state == "replaying"
    assert stats.error_count == 1
    assert stats.last_error_class == "parse_error"
    assert not hasattr(stats, "subscribed_symbols")
    assert not hasattr(stats, "subscribers")
    assert not hasattr(stats, "events")
