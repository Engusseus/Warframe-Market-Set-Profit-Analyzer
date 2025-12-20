"""Unit tests for profit calculation."""
import pytest

from app.core.profit_calculator import (
    calculate_profit_margins,
    calculate_profit_margins_dict,
)
from app.models.schemas import ProfitData, PartDetail


class TestCalculateProfitMargins:
    """Tests for calculate_profit_margins function."""

    @pytest.mark.unit
    def test_calculates_profit_margin_correctly(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that profit margin is calculated correctly."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        assert len(result) > 0
        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None

        # Set price: 150, Part costs: 4 * 25 = 100
        # Profit margin: 150 - 100 = 50
        assert saryn.profit_margin == 50.0
        assert saryn.set_price == 150.0
        assert saryn.part_cost == 100.0

    @pytest.mark.unit
    def test_calculates_profit_percentage_correctly(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that profit percentage (ROI) is calculated correctly."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None

        # Profit margin: 50, Part cost: 100
        # Profit percentage: (50 / 100) * 100 = 50%
        assert saryn.profit_percentage == 50.0

    @pytest.mark.unit
    def test_returns_profit_data_objects(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that returns ProfitData objects."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        for item in result:
            assert isinstance(item, ProfitData)

    @pytest.mark.unit
    def test_includes_part_details(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that part details are included."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None
        assert len(saryn.part_details) == 4

        for part in saryn.part_details:
            assert isinstance(part, PartDetail)
            assert part.unit_price == 25.0
            assert part.quantity == 1
            assert part.total_cost == 25.0

    @pytest.mark.unit
    def test_handles_quantity_in_set(self):
        """Test that quantity_in_set is properly multiplied."""
        set_prices = [{"slug": "test_set", "lowest_price": 100.0}]
        part_prices = [
            {"slug": "test_part", "lowest_price": 10.0, "quantity_in_set": 3},
        ]
        detailed_sets = [{
            "id": "test_set",
            "slug": "test_set",
            "name": "Test Set",
            "setParts": [
                {"code": "test_part", "name": "Test Part", "quantityInSet": 3},
            ],
        }]

        result = calculate_profit_margins(set_prices, part_prices, detailed_sets)

        assert len(result) == 1
        # Part cost: 10 * 3 = 30
        # Profit margin: 100 - 30 = 70
        assert result[0].part_cost == 30.0
        assert result[0].profit_margin == 70.0

    @pytest.mark.unit
    def test_skips_sets_with_missing_parts(self):
        """Test that sets with missing part prices are skipped."""
        set_prices = [{"slug": "incomplete_set", "lowest_price": 100.0}]
        part_prices = []  # No part prices
        detailed_sets = [{
            "id": "incomplete_set",
            "slug": "incomplete_set",
            "name": "Incomplete Set",
            "setParts": [
                {"code": "missing_part", "name": "Missing Part", "quantityInSet": 1},
            ],
        }]

        result = calculate_profit_margins(set_prices, part_prices, detailed_sets)
        assert len(result) == 0

    @pytest.mark.unit
    def test_skips_sets_not_in_price_data(self):
        """Test that sets without price data are skipped."""
        set_prices = []  # No set prices
        part_prices = [
            {"slug": "some_part", "lowest_price": 10.0},
        ]
        detailed_sets = [{
            "id": "unparsed_set",
            "slug": "unparsed_set",
            "name": "Unparsed Set",
            "setParts": [
                {"code": "some_part", "name": "Some Part", "quantityInSet": 1},
            ],
        }]

        result = calculate_profit_margins(set_prices, part_prices, detailed_sets)
        assert len(result) == 0

    @pytest.mark.unit
    def test_empty_inputs_return_empty(self):
        """Test that empty inputs return empty list."""
        assert calculate_profit_margins([], [], []) == []
        assert calculate_profit_margins([], [{"slug": "x", "lowest_price": 1}], []) == []
        assert calculate_profit_margins([{"slug": "x", "lowest_price": 1}], [], []) == []

    @pytest.mark.unit
    def test_handles_negative_profit(self):
        """Test that negative profit margins are calculated correctly."""
        set_prices = [{"slug": "losing_set", "lowest_price": 50.0}]
        part_prices = [
            {"slug": "expensive_part", "lowest_price": 30.0, "quantity_in_set": 2},
        ]
        detailed_sets = [{
            "id": "losing_set",
            "slug": "losing_set",
            "name": "Losing Set",
            "setParts": [
                {"code": "expensive_part", "name": "Expensive Part", "quantityInSet": 2},
            ],
        }]

        result = calculate_profit_margins(set_prices, part_prices, detailed_sets)

        assert len(result) == 1
        # Part cost: 30 * 2 = 60
        # Profit margin: 50 - 60 = -10
        assert result[0].profit_margin == -10.0
        assert result[0].profit_percentage < 0


class TestCalculateProfitMarginsDict:
    """Tests for calculate_profit_margins_dict function."""

    @pytest.mark.unit
    def test_returns_dict_format(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that returns list of dictionaries."""
        result = calculate_profit_margins_dict(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        for item in result:
            assert isinstance(item, dict)
            assert 'set_slug' in item
            assert 'profit_margin' in item
            assert 'part_details' in item

    @pytest.mark.unit
    def test_dict_format_matches_pydantic(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Test that dict format has same values as Pydantic version."""
        pydantic_result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )
        dict_result = calculate_profit_margins_dict(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        assert len(pydantic_result) == len(dict_result)

        for pyd, dct in zip(pydantic_result, dict_result):
            assert pyd.set_slug == dct['set_slug']
            assert pyd.profit_margin == dct['profit_margin']
            assert pyd.profit_percentage == dct['profit_percentage']
