import asyncio

import httpx
import pytest

from wf_market_analyzer import (
    AnalysisReport,
    RuntimeConfig,
    SetProfitAnalyzer,
    WarframeMarketClient,
)


def make_transport(
    *,
    items_status_sequence: tuple[int, ...] = (200,),
    item_payload: object | None = None,
    invalid_quantity: bool = False,
    alpha_set_prices: list[dict[str, object]] | None = None,
    alpha_blueprint_prices: list[dict[str, object]] | None = None,
    alpha_barrel_prices: list[dict[str, object]] | None = None,
    beta_stats_missing: bool = True,
    use_hours48_alias: bool = False,
    invalid_volume: bool = False,
    malformed_volume_entry: bool = False,
) -> tuple[httpx.MockTransport, dict[str, int]]:
    attempts = {"items": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v2/items":
            attempts["items"] += 1
            index = min(attempts["items"] - 1, len(items_status_sequence) - 1)
            status = items_status_sequence[index]
            if status != 200:
                return httpx.Response(status, json={"error": f"status {status}"})

            payload = item_payload
            if payload is None:
                payload = {
                    "data": [
                        {"slug": "alpha_prime_set"},
                        {"slug": "alpha_prime_blueprint"},
                        {"slug": "beta_prime_set"},
                    ]
                }
            return httpx.Response(200, json=payload)

        if path == "/v2/item/alpha_prime_set/set":
            blueprint_quantity: object = "bad" if invalid_quantity else 1
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "slug": "alpha_prime_set",
                                "i18n": {"en": {"name": "Alpha Prime Set"}},
                            },
                            {
                                "slug": "alpha_prime_blueprint",
                                "quantityInSet": blueprint_quantity,
                                "i18n": {"en": {"name": "Alpha Prime Blueprint"}},
                            },
                            {
                                "slug": "alpha_prime_barrel",
                                "quantityInSet": 2,
                                "i18n": {"en": {"name": "Alpha Prime Barrel"}},
                            },
                        ]
                    }
                },
            )

        if path == "/v2/item/beta_prime_set/set":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "items": [
                            {
                                "slug": "beta_prime_set",
                                "i18n": {"en": {"name": "Beta Prime Set"}},
                            },
                            {
                                "slug": "beta_prime_blueprint",
                                "quantityInSet": 1,
                                "i18n": {"en": {"name": "Beta Prime Blueprint"}},
                            },
                        ]
                    }
                },
            )

        if path == "/v2/orders/item/alpha_prime_set/top":
            sell = alpha_set_prices or [
                {"platinum": 120, "quantity": 1},
                {"platinum": 100, "quantity": 1},
                {"platinum": 110, "quantity": 1},
            ]
            return httpx.Response(200, json={"data": {"sell": sell, "buy": []}})

        if path == "/v2/orders/item/alpha_prime_blueprint/top":
            sell = alpha_blueprint_prices or [{"platinum": 10}, {"platinum": 12}]
            return httpx.Response(200, json={"data": {"sell": sell, "buy": []}})

        if path == "/v2/orders/item/alpha_prime_barrel/top":
            sell = alpha_barrel_prices or [{"platinum": 5}, {"platinum": 7}]
            return httpx.Response(200, json={"data": {"sell": sell, "buy": []}})

        if path == "/v2/orders/item/beta_prime_set/top":
            return httpx.Response(
                200,
                json={"data": {"sell": [{"platinum": 70}, {"platinum": 75}], "buy": []}},
            )

        if path == "/v2/orders/item/beta_prime_blueprint/top":
            return httpx.Response(
                200,
                json={"data": {"sell": [{"platinum": 20}, {"platinum": 22}], "buy": []}},
            )

        if path == "/v1/items/alpha_prime_set/statistics":
            entries: list[object] = [{"volume": 5}, {"volume": 7}]
            if malformed_volume_entry:
                entries = [{"volume": 5}, "bad-entry"]
            if invalid_volume:
                entries = [{"volume": 5}, {"volume": "bad"}]

            stats_key = "hours48" if use_hours48_alias else "48hours"
            return httpx.Response(
                200,
                json={"payload": {"statistics_closed": {stats_key: entries}}},
            )

        if path == "/v1/items/beta_prime_set/statistics":
            if beta_stats_missing:
                return httpx.Response(200, json={"payload": {}})
            return httpx.Response(
                200,
                json={
                    "payload": {"statistics_closed": {"48hours": [{"volume": 2}]}}
                },
            )

        return httpx.Response(404, json={"error": f"Unexpected path {path}"})

    return httpx.MockTransport(handler), attempts


async def immediate_sleep(_: float) -> None:
    return None


def run(coro):
    return asyncio.run(coro)


def test_client_retries_documented_transient_509(monkeypatch):
    monkeypatch.setattr("wf_market_analyzer.asyncio.sleep", immediate_sleep)
    transport, attempts = make_transport(items_status_sequence=(509, 200))
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=2, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_all_prime_set_slugs()
        finally:
            await client.close()

    slugs = run(scenario())

    assert slugs == ["alpha_prime_set", "beta_prime_set"]
    assert attempts["items"] == 2


def test_client_handles_http_error_invalid_json_and_non_dict_payload(monkeypatch):
    monkeypatch.setattr("wf_market_analyzer.asyncio.sleep", immediate_sleep)

    def failing_handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    def invalid_json_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="{not-json")

    def list_payload_handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=["not-a-dict"])

    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def exercise(transport: httpx.BaseTransport):
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client._get_json("https://example.test/endpoint")
        finally:
            await client.close()

    assert run(exercise(httpx.MockTransport(failing_handler))) is None
    assert run(exercise(httpx.MockTransport(invalid_json_handler))) is None
    assert run(exercise(httpx.MockTransport(list_payload_handler))) is None


def test_client_returns_none_for_404():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "missing"})

    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=httpx.MockTransport(handler))
        try:
            return await client._get_json("https://example.test/missing")
        finally:
            await client.close()

    assert run(scenario()) is None


def test_client_rejects_non_list_item_catalog():
    transport, _ = make_transport(item_payload={"data": "bad"})
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            await client.fetch_all_prime_set_slugs()
        finally:
            await client.close()

    with pytest.raises(RuntimeError):
        run(scenario())


def test_client_parses_set_membership_and_quantities():
    transport, _ = make_transport()
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_set_data("alpha_prime_set")
        finally:
            await client.close()

    set_data = run(scenario())

    assert set_data is not None
    assert set_data.name == "Alpha Prime Set"
    assert set_data.parts == {
        "alpha_prime_blueprint": 1,
        "alpha_prime_barrel": 2,
    }
    assert set_data.part_names["alpha_prime_barrel"] == "Alpha Prime Barrel"


def test_fetch_set_data_skips_invalid_quantity():
    transport, _ = make_transport(invalid_quantity=True)
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_set_data("alpha_prime_set")
        finally:
            await client.close()

    assert run(scenario()) is None


def test_fetch_top_sell_prices_uses_price_fallback_and_filters_invalid_values():
    transport, _ = make_transport(
        alpha_blueprint_prices=[
            {"price": "10"},
            {"platinum": 12},
            {"platinum": 0},
            {"price": -1},
            {"price": "nan"},
        ]
    )
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_top_sell_prices("alpha_prime_blueprint")
        finally:
            await client.close()

    assert run(scenario()) == [10.0, 12.0]


def test_fetch_top_sell_prices_returns_empty_for_malformed_payload():
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"sell": "bad"}})

    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=httpx.MockTransport(handler))
        try:
            return await client.fetch_top_sell_prices("broken_item")
        finally:
            await client.close()

    assert run(scenario()) == []


def test_fetch_volume_48h_accepts_hours48_alias():
    transport, _ = make_transport(use_hours48_alias=True)
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_volume_48h("alpha_prime_set")
        finally:
            await client.close()

    assert run(scenario()) == 12


@pytest.mark.parametrize(
    ("invalid_volume", "malformed_volume_entry"),
    [(True, False), (False, True)],
)
def test_fetch_volume_48h_rejects_invalid_entries(invalid_volume, malformed_volume_entry):
    transport, _ = make_transport(
        invalid_volume=invalid_volume,
        malformed_volume_entry=malformed_volume_entry,
    )
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_volume_48h("alpha_prime_set")
        finally:
            await client.close()

    assert run(scenario()) is None


def test_analyzer_runs_end_to_end_and_skips_sets_with_missing_statistics():
    transport, _ = make_transport()
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        analyzer = SetProfitAnalyzer(settings, transport=transport)
        return await analyzer.analyze()

    report = run(scenario())

    assert isinstance(report, AnalysisReport)
    assert report.completed_at.tzinfo is not None
    assert len(report.results) == 1
    assert report.catalog_set_count == 2
    assert report.metadata_set_count == 2
    assert report.skipped_invalid_set_count == 0
    assert report.skipped_missing_price_count == 0
    assert report.skipped_missing_volume_count == 1

    result = report.results[0]
    assert result.set_data.slug == "alpha_prime_set"
    assert result.price_data.set_price == 105.0
    assert result.price_data.total_part_cost == 23.0
    assert result.price_data.profit == 82.0
    assert result.volume_data.volume_48h == 12


def test_analyzer_rejects_thin_orderbooks_by_default():
    transport, _ = make_transport(alpha_set_prices=[{"platinum": 120}])
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        analyzer = SetProfitAnalyzer(settings, transport=transport)
        await analyzer.analyze()

    with pytest.raises(RuntimeError, match="No analyzable sets"):
        run(scenario())


def test_analyzer_allows_thin_orderbooks_when_enabled():
    transport, _ = make_transport(alpha_set_prices=[{"platinum": 120}])
    settings = RuntimeConfig(
        requests_per_second=1000.0,
        max_retries=1,
        debug=False,
        allow_thin_orderbooks=True,
    )

    async def scenario():
        analyzer = SetProfitAnalyzer(settings, transport=transport)
        return await analyzer.analyze()

    report = run(scenario())

    assert len(report.results) == 1
    assert report.results[0].price_data.set_price == 120.0


def test_analyzer_raises_when_metadata_is_invalid():
    transport, _ = make_transport(invalid_quantity=True, beta_stats_missing=False)
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def scenario():
        analyzer = SetProfitAnalyzer(settings, transport=transport)
        return await analyzer.analyze()

    report = run(scenario())

    assert report.metadata_set_count == 1
    assert report.skipped_invalid_set_count == 1
    assert report.results[0].set_data.slug == "beta_prime_set"
