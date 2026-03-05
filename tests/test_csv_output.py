import csv
from datetime import datetime

from wf_market_analyzer import (
    PriceData,
    ResultRow,
    SetData,
    VolumeData,
    build_output_path,
    write_results_to_csv,
)


def sample_result(score: float = 0.8123) -> ResultRow:
    return ResultRow(
        set_data=SetData(
            slug="alpha_prime_set",
            name="Alpha Prime Set",
            parts={
                "alpha_prime_blueprint": 1,
                "alpha_prime_barrel": 2,
            },
            part_names={
                "alpha_prime_blueprint": "Alpha Prime Blueprint",
                "alpha_prime_barrel": "Alpha Prime Barrel",
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
        run_timestamp="2026-03-05T14:15:16-05:00",
    )


def test_build_output_path_uses_timestamped_filename(tmp_path):
    completed_at = datetime.fromisoformat("2026-03-05T14:15:16-05:00")

    output_path = build_output_path(tmp_path, completed_at)

    assert output_path.name == "set_profit_analysis_20260305_141516.csv"


def test_write_results_to_csv_writes_expected_columns(tmp_path):
    completed_at = datetime.fromisoformat("2026-03-05T14:15:16-05:00")
    output_path = build_output_path(tmp_path, completed_at)

    write_results_to_csv([sample_result()], output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 1
    assert rows[0]["Run Timestamp"] == "2026-03-05T14:15:16-05:00"
    assert rows[0]["Set Name"] == "Alpha Prime Set"
    assert rows[0]["Set Slug"] == "alpha_prime_set"
    assert rows[0]["Profit"] == "88.0"
    assert rows[0]["Score"] == "0.8123"
    assert rows[0]["Part Prices"] == (
        "Alpha Prime Blueprint (x1): 11.0; Alpha Prime Barrel (x2): 3.0"
    )
