import argparse
import logging

import pytest

from wf_market_analyzer import (
    PriceData,
    ResultRow,
    RunIdFilter,
    SetData,
    VolumeData,
    bool_arg,
    build_request_headers,
    calculate_average_sell_price,
    env_var_name,
    extract_item_name,
    extract_set_items,
    generate_run_id,
    log_level_arg,
    non_empty_string,
    non_negative_finite_float,
    non_negative_int,
    parse_required_non_negative_int,
    parse_required_positive_int,
    positive_float,
    positive_int,
    safe_float,
    score_results,
)


def make_result(slug: str, profit: float, volume: int) -> ResultRow:
    return ResultRow(
        set_data=SetData(
            slug=slug,
            name=slug.replace("_", " ").title(),
            parts={},
            part_names={},
        ),
        price_data=PriceData(
            set_price=0.0,
            part_prices={},
            total_part_cost=0.0,
            profit=profit,
        ),
        volume_data=VolumeData(volume_48h=volume),
        score=0.0,
        run_timestamp="2026-03-05T14:15:16-05:00",
    )


def test_generate_run_id_and_build_request_headers():
    run_id = generate_run_id()
    headers = build_request_headers("pc", "en", True)

    assert len(run_id) == 8
    assert headers == {
        "Platform": "pc",
        "Language": "en",
        "Crossplay": "true",
        "Accept": "application/json",
    }


def test_run_id_filter_injects_run_id():
    record = logging.LogRecord("wf", logging.INFO, __file__, 1, "hello", (), None)

    filtered = RunIdFilter("run12345").filter(record)

    assert filtered is True
    assert record.run_id == "run12345"


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        ("2.5", 0.0, 2.5),
        (None, 1.0, 1.0),
        ("nan", 3.0, 3.0),
        ("inf", 4.0, 4.0),
    ],
)
def test_safe_float(value, default, expected):
    assert safe_float(value, default=default) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2", 2), ("2.0", 2), (1, 1), ("0", None), ("-1", None), ("bad", None)],
)
def test_parse_required_positive_int(value, expected):
    assert parse_required_positive_int(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2", 2), ("0", 0), (0, 0), ("-1", None), ("2.5", None), ("bad", None)],
)
def test_parse_required_non_negative_int(value, expected):
    assert parse_required_non_negative_int(value) == expected


def test_extract_item_name_uses_i18n_then_name_then_slug():
    assert extract_item_name({"i18n": {"en": {"name": "Alpha Prime Set"}}}, "alpha_prime_set") == "Alpha Prime Set"
    assert extract_item_name({"name": "Fallback Name"}, "alpha_prime_set") == "Fallback Name"
    assert extract_item_name({}, "alpha_prime_set") == "Alpha Prime Set"


def test_extract_set_items_handles_supported_shapes():
    payload_list = [{"slug": "alpha"}]
    payload_items = {"items": [{"slug": "beta"}]}
    payload_set = {"set": [{"slug": "gamma"}]}

    assert extract_set_items(payload_list) == payload_list
    assert extract_set_items(payload_items) == payload_items["items"]
    assert extract_set_items(payload_set) == payload_set["set"]
    assert extract_set_items("bad") == []


def test_calculate_average_sell_price_respects_sample_requirements():
    assert calculate_average_sell_price([10.0, 20.0, 30.0], 2) == 15.0
    assert calculate_average_sell_price([10.0], 2) is None
    assert calculate_average_sell_price([10.0], 2, allow_thin_orderbooks=True) == 10.0
    assert calculate_average_sell_price([-1.0, 0.0], 2) is None


def test_score_results_uses_weighted_min_max_normalization():
    low = make_result("alpha_prime_set", 20.0, 5)
    high = make_result("beta_prime_set", 80.0, 25)
    rows = [low, high]

    score_results(rows, profit_weight=1.0, volume_weight=1.2)

    assert low.score == 0.0
    assert high.score == 2.2


def test_score_results_handles_zero_ranges_without_dividing():
    first = make_result("alpha_prime_set", 20.0, 10)
    second = make_result("beta_prime_set", 20.0, 10)
    rows = [first, second]

    score_results(rows, profit_weight=1.0, volume_weight=1.2)

    assert first.score == 0.0
    assert second.score == 0.0


def test_score_results_accepts_empty_rows():
    score_results([], profit_weight=1.0, volume_weight=1.2)


@pytest.mark.parametrize(
    ("parser", "value", "expected"),
    [
        (positive_int, "2", 2),
        (non_negative_int, "0", 0),
        (positive_float, "2.5", 2.5),
        (non_negative_finite_float, "0", 0.0),
        (non_empty_string, " hello ", "hello"),
        (log_level_arg, "debug", "DEBUG"),
        (bool_arg, "yes", True),
        (bool_arg, "off", False),
    ],
)
def test_validators_accept_expected_values(parser, value, expected):
    assert parser(value) == expected


@pytest.mark.parametrize(
    ("parser", "value"),
    [
        (positive_int, "0"),
        (non_negative_int, "-1"),
        (positive_float, "0"),
        (non_negative_finite_float, "-1"),
        (non_empty_string, "   "),
        (log_level_arg, "verbose"),
        (bool_arg, "maybe"),
    ],
)
def test_validators_reject_invalid_values(parser, value):
    with pytest.raises(argparse.ArgumentTypeError):
        parser(value)


def test_env_var_name_is_namespaced():
    assert env_var_name("OUTPUT_DIR") == "WF_MARKET_ANALYZER_OUTPUT_DIR"
