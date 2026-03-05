import asyncio

import httpx
import pytest

from wf_market_analyzer import (
    RuntimeConfig,
    SetProfitAnalyzer,
    WarframeMarketClient,
    parse_args,
)


def make_transport(rate_limit_items_once: bool = True):
    attempts = {"items": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/v2/items":
            attempts["items"] += 1
            if rate_limit_items_once and attempts["items"] == 1:
                return httpx.Response(429, json={"error": "rate limited"})
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"slug": "alpha_prime_set"},
                        {"slug": "alpha_prime_blueprint"},
                        {"slug": "beta_prime_set"},
                    ]
                },
            )

        if path == "/v2/item/alpha_prime_set/set":
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
                                "quantityInSet": 1,
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
            return httpx.Response(
                200,
                json={
                    "data": {
                        "sell": [
                            {"platinum": 120, "quantity": 1},
                            {"platinum": 100, "quantity": 1},
                            {"platinum": 110, "quantity": 1},
                        ],
                        "buy": [],
                    }
                },
            )

        if path == "/v2/orders/item/alpha_prime_blueprint/top":
            return httpx.Response(
                200,
                json={"data": {"sell": [{"platinum": 10}, {"platinum": 12}], "buy": []}},
            )

        if path == "/v2/orders/item/alpha_prime_barrel/top":
            return httpx.Response(
                200,
                json={"data": {"sell": [{"platinum": 5}, {"platinum": 7}], "buy": []}},
            )

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
            return httpx.Response(
                200,
                json={
                    "payload": {
                        "statistics_closed": {
                            "48hours": [
                                {"volume": 5},
                                {"volume": 7},
                            ]
                        }
                    }
                },
            )

        if path == "/v1/items/beta_prime_set/statistics":
            return httpx.Response(200, json={"payload": {}})

        return httpx.Response(404, json={"error": f"Unexpected path {path}"})

    return httpx.MockTransport(handler), attempts


def test_client_retries_prime_set_fetch_and_filters_prime_sets():
    transport, attempts = make_transport()
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=3, debug=False)

    async def run_test():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            slugs = await client.fetch_all_prime_set_slugs()
        finally:
            await client.close()
        return slugs

    slugs = asyncio.run(run_test())

    assert slugs == ["alpha_prime_set", "beta_prime_set"]
    assert attempts["items"] == 2


def test_client_parses_set_membership_and_quantities():
    transport, _ = make_transport()
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def run_test():
        client = WarframeMarketClient(settings, transport=transport)
        try:
            return await client.fetch_set_data("alpha_prime_set")
        finally:
            await client.close()

    set_data = asyncio.run(run_test())

    assert set_data is not None
    assert set_data.name == "Alpha Prime Set"
    assert set_data.parts == {
        "alpha_prime_blueprint": 1,
        "alpha_prime_barrel": 2,
    }
    assert set_data.part_names["alpha_prime_barrel"] == "Alpha Prime Barrel"


def test_analyzer_runs_end_to_end_and_skips_sets_with_missing_statistics():
    transport, _ = make_transport(rate_limit_items_once=False)
    settings = RuntimeConfig(requests_per_second=1000.0, max_retries=1, debug=False)

    async def run_test():
        analyzer = SetProfitAnalyzer(settings, transport=transport)
        return await analyzer.analyze()

    results, completed_at = asyncio.run(run_test())

    assert completed_at.tzinfo is not None
    assert len(results) == 1

    result = results[0]
    assert result.set_data.slug == "alpha_prime_set"
    assert result.price_data.set_price == 105.0
    assert result.price_data.total_part_cost == 23.0
    assert result.price_data.profit == 82.0
    assert result.volume_data.volume_48h == 12


def test_parse_args_rejects_price_sample_size_above_top_endpoint_limit():
    with pytest.raises(SystemExit):
        parse_args(["--price-sample-size", "6"])
