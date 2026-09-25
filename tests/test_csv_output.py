import csv
from datetime import datetime

import pytest

from wf_market_analyzer import (
    PriceData,
    ResultRow,
    SetData,
    VolumeData,
    build_output_path,
    format_part_prices,
    sanitize_spreadsheet_cell,
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


@pytest.mark.parametrize("profit", [88.0, -88.0])
def test_write_results_to_csv_writes_expected_columns_atomically(tmp_path, profit):
    output_path = tmp_path / "results.csv"
    output_path.write_text("old-data", encoding="utf-8")
    result = sample_result()
    result.price_data.profit = profit

    write_results_to_csv([result], output_path)

    leftovers = list(tmp_path.glob(".*.tmp"))
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert leftovers == []
    assert len(rows) == 1
    assert rows[0]["Run Timestamp"] == "2026-03-05T14:15:16-05:00"
    assert rows[0]["Set Name"] == "Alpha Prime Set"
    assert rows[0]["Set Slug"] == "alpha_prime_set"
    assert rows[0]["Profit"] == f"{profit:.1f}"
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


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "\t", "\r", "\n"])
def test_sanitize_spreadsheet_cell_escapes_formula_prefixes(prefix):
    value = f"{prefix}malicious formula"

    assert sanitize_spreadsheet_cell(value) == f"'{value}"


@pytest.mark.parametrize("value", [
    "",
    "Alpha Prime Set",
    "alpha_prime_set",
    "Équinoxe Prime",
    'Alpha "Prime", Set; Parts',
    "Alpha-Prime + Beta @ 10",
    "Alpha Prime Blueprint (x1): 11.0; alpha_prime_barrel (x2): 3.0",
])
def test_sanitize_spreadsheet_cell_preserves_ordinary_text(value):
    assert sanitize_spreadsheet_cell(value) == value


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
@pytest.mark.parametrize("field", [
    "set_name", "set_slug", "first_part_name", "later_part_name", "part_slug",
])
@pytest.mark.parametrize("payload", [
    "\n=1+1",
    "=1+1",
    "Safe;=1+1;",
    "Safe; =1+1;",
    'Safe;"=1+1";',
    'Safe; "=1+1";',
    "Safe;\t=1+1;",
    "Safe\r\n=1+1",
    "Safe\t=1+1\t",
    "Safe,=1+1,",
    "Safe;=1+1;+1+1;-1+1;@SUM(1);",
])
def test_write_results_to_csv_neutralizes_formulas_at_import_boundaries(
    tmp_path, delimiter, field, payload,
):
    result = sample_result()
    if field == "set_name":
        result.set_data.name = payload
    elif field == "set_slug":
        result.set_data.slug = payload
    elif field == "part_slug":
        part_slug = "alpha_prime_barrel"
        result.set_data.parts[payload] = result.set_data.parts.pop(part_slug)
        result.price_data.part_prices[payload] = result.price_data.part_prices.pop(part_slug)
    else:
        part_slug = (
            "alpha_prime_blueprint" if field == "first_part_name" else "alpha_prime_barrel"
        )
        result.set_data.part_names[part_slug] = payload
    output_path = tmp_path / "sanitized.csv"

    write_results_to_csv([result], output_path)

    # Parse the entire artifact: quoting differs when the importer uses another delimiter.
    with output_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter, skipinitialspace=True))

    assert len(rows) >= 2
    for row in rows:
        for cell in row:
            assert not cell.startswith(("=", "+", "-", "@", "\t", "\r", "\n")), repr(cell)


def test_write_results_to_csv_sanitizes_untrusted_text(tmp_path):
    result = sample_result(slug='=HYPERLINK("https://example.test")_prime_set')
    result.set_data.name = '+WEBSERVICE("https://example.test")'
    first_part = next(iter(result.set_data.parts))
    result.set_data.part_names[first_part] = "@SUM(1+1)"
    output_path = tmp_path / "sanitized.csv"

    write_results_to_csv([result], output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))

    assert row["Set Name"].startswith("'+")
    assert row["Set Slug"].startswith("'=")
    assert row["Part Prices"].startswith("'@")


def test_write_results_to_csv_escapes_spreadsheet_formulas(tmp_path):
    output_path = tmp_path / "formulas.csv"
    formula_triggers = ("=", "+", "-", "@", "\t", "\r", "\n")
    results = []

    for index, trigger in enumerate(formula_triggers):
        result = sample_result(slug=f"{trigger}malicious_slug_{index}_prime_set")
        result.set_data.name = f"{trigger}malicious set name"
        first_part = next(iter(result.set_data.parts))
        result.set_data.part_names[first_part] = f"{trigger}malicious part name"
        results.append(result)

    write_results_to_csv(results, output_path)

    with output_path.open(newline="", encoding="utf-8") as handle:
        csv_rows = list(csv.DictReader(handle))

    for row, trigger in zip(csv_rows, formula_triggers, strict=True):
        assert row["Set Name"].startswith(f"'{trigger}")
        assert row["Set Slug"].startswith(f"'{trigger}")
        assert row["Part Prices"].startswith(f"'{trigger}")


def test_format_part_prices_handles_empty_parts():
    result = ResultRow(
        set_data=SetData(slug="empty", name="Empty", parts={}, part_names={}),
        price_data=PriceData(set_price=1.0, part_prices={}, total_part_cost=0.0, profit=1.0),
        volume_data=VolumeData(volume_48h=1),
        score=0.0,
        run_timestamp="2026-03-05T14:15:16-05:00",
    )

    assert format_part_prices(result) == ""
