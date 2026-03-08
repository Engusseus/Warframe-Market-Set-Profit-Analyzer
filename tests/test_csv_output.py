import csv
from datetime import datetime

from wf_market_analyzer import (
    PriceData,
    ResultRow,
    SetData,
    VolumeData,
    build_output_path,
    format_part_prices,
    write_results_to_csv,
)


def sample_result(
    *,
    slug: str = "alpha_prime_set",
    score: float = 0.8123,
    run_timestamp: str = "2026-03-05T14:15:16-05:00",
) -> ResultRow:
    return ResultRow(
        set_data=SetData(
            slug=slug,
            name=slug.replace("_", " ").title(),
            parts={
                "alpha_prime_blueprint": 1,
                "alpha_prime_barrel": 2,
            },
            part_names={
                "alpha_prime_blueprint": "Alpha Prime Blueprint",
            },
        ),
        price_data=PriceData(
            set_price=105.0,
            part_prices={
                "alpha_prime_blueprint": 11.0,
                "alpha_prime_barrel": 3.0,
            },
            total_part_cost=17.0,
            profit=88.0,
        ),
        volume_data=VolumeData(volume_48h=12),
        score=score,
        run_timestamp=run_timestamp,
    )


def test_build_output_path_uses_timestamped_filename(tmp_path):
    completed_at = datetime.fromisoformat("2026-03-05T14:15:16-05:00")

    output_path = build_output_path(tmp_path, completed_at)

    assert output_path.name == "set_profit_analysis_20260305_141516.csv"


def test_build_output_path_appends_suffix_when_timestamp_exists(tmp_path):
    completed_at = datetime.fromisoformat("2026-03-05T14:15:16-05:00")
    existing = tmp_path / "set_profit_analysis_20260305_141516.csv"
    existing.write_text("already here", encoding="utf-8")

    output_path = build_output_path(tmp_path, completed_at)

    assert output_path.name == "set_profit_analysis_20260305_141516_1.csv"


def test_build_output_path_respects_output_file_and_run_id(tmp_path):
    completed_at = datetime.fromisoformat("2026-03-05T14:15:16-05:00")

    explicit = build_output_path(
        tmp_path,
        completed_at,
        output_file=tmp_path / "explicit.csv",
    )
    with_run_id = build_output_path(tmp_path, completed_at, run_id="abc12345")

    assert explicit == tmp_path / "explicit.csv"
    assert with_run_id.name == "set_profit_analysis_20260305_141516_abc12345.csv"


def test_write_results_to_csv_writes_expected_columns_atomically(tmp_path):
    output_path = tmp_path / "results.csv"
    output_path.write_text("old-data", encoding="utf-8")

    write_results_to_csv([sample_result()], output_path)

    leftovers = list(tmp_path.glob(".*.tmp"))
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert leftovers == []
    assert len(rows) == 1
    assert rows[0]["Run Timestamp"] == "2026-03-05T14:15:16-05:00"
    assert rows[0]["Set Name"] == "Alpha Prime Set"
    assert rows[0]["Set Slug"] == "alpha_prime_set"
    assert rows[0]["Profit"] == "88.0"
    assert rows[0]["Score"] == "0.8123"
    assert rows[0]["Part Prices"] == (
        "Alpha Prime Blueprint (x1): 11.0; alpha_prime_barrel (x2): 3.0"
    )


def test_write_results_to_csv_preserves_row_order(tmp_path):
    output_path = tmp_path / "ordered.csv"
    rows = [
        sample_result(slug="beta_prime_set", score=2.2),
        sample_result(slug="alpha_prime_set", score=0.2),
    ]

    write_results_to_csv(rows, output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))

    assert [row["Set Slug"] for row in csv_rows] == [
        "beta_prime_set",
        "alpha_prime_set",
    ]


def test_format_part_prices_handles_empty_parts():
    result = ResultRow(
        set_data=SetData(slug="empty", name="Empty", parts={}, part_names={}),
        price_data=PriceData(set_price=1.0, part_prices={}, total_part_cost=0.0, profit=1.0),
        volume_data=VolumeData(volume_48h=1),
        score=0.0,
        run_timestamp="2026-03-05T14:15:16-05:00",
    )

    assert format_part_prices(result) == ""
