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
    def test_calculates_instant_profit_margin_correctly(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Canonical margin should use instant execution metrics."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        assert len(result) > 0
        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None

        # Instant revenue uses top bid: 130.
        # Instant part cost uses top asks: 4 * 25 = 100.
        assert saryn.profit_margin == pytest.approx(30.0)
        assert saryn.set_price == pytest.approx(130.0)
        assert saryn.part_cost == pytest.approx(100.0)

    @pytest.mark.unit
    def test_calculates_instant_profit_percentage_correctly(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Canonical ROI should use instant execution metrics."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None

        # Instant ROI: (130 - 100) / 100 * 100
        assert saryn.profit_percentage == pytest.approx(30.0)

    @pytest.mark.unit
    def test_populates_instant_and_patient_metrics(
        self, sample_set_prices, sample_part_prices, sample_detailed_sets
    ):
        """Instant and patient metrics should both be present and coherent."""
        result = calculate_profit_margins(
            set_prices=sample_set_prices,
            part_prices=sample_part_prices,
            detailed_sets=sample_detailed_sets,
        )

        saryn = next((r for r in result if r.set_slug == "saryn_prime_set"), None)
        assert saryn is not None

        assert saryn.instant_set_price == pytest.approx(130.0)
        assert saryn.instant_part_cost == pytest.approx(100.0)
        assert saryn.instant_profit_margin == pytest.approx(30.0)
        assert saryn.instant_profit_percentage == pytest.approx(30.0)

        assert saryn.patient_set_price == pytest.approx(150.0)
        assert saryn.patient_part_cost == pytest.approx(80.0)
        assert saryn.patient_profit_margin == pytest.approx(70.0)
        assert saryn.patient_profit_percentage == pytest.approx(87.5)

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
            assert part.unit_price == pytest.approx(25.0)
            assert part.quantity == 1
            assert part.total_cost == pytest.approx(25.0)
            assert part.highest_bid == pytest.approx(20.0)
            assert len(part.top_sell_orders) > 0
            assert len(part.top_buy_orders) > 0
            assert part.instant_unit_price == pytest.approx(25.0)
            assert part.patient_unit_price == pytest.approx(20.0)

    @pytest.mark.unit
    def test_handles_quantity_in_set_with_depth_vwap(self):
        """Required quantity should consume multiple orderbook levels."""
        set_prices = [{
            "slug": "test_set",
            "lowest_price": 110.0,
            "highest_bid": 100.0,
            "top_sell_orders": [{"platinum": 110.0, "quantity": 2}],
            "top_buy_orders": [{"platinum": 100.0, "quantity": 1}],
        }]
        part_prices = [
            {
                "slug": "test_part",
                "lowest_price": 10.0,
                "highest_bid": 8.0,
                "quantity_in_set": 3,
                "top_sell_orders": [
                    {"platinum": 10.0, "quantity": 1},
                    {"platinum": 12.0, "quantity": 2},
                ],
                "top_buy_orders": [
                    {"platinum": 8.0, "quantity": 2},
                    {"platinum": 7.0, "quantity": 3},
                ],
            },
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
        # Instant part cost: 1x10 + 2x12 = 34
        # Instant set revenue: 1x100
        assert result[0].part_cost == pytest.approx(34.0)
        assert result[0].profit_margin == pytest.approx(66.0)

        # Patient part cost: 2x8 + 1x7 = 23
        # Patient set revenue: 1x110
        assert result[0].patient_part_cost == pytest.approx(23.0)
        assert result[0].patient_profit_margin == pytest.approx(87.0)

    @pytest.mark.unit
    def test_falls_back_when_orderbook_missing(self):
        """Missing orderbook levels should fallback to lowest_price/highest_bid."""
        set_prices = [{"slug": "test_set", "lowest_price": 120.0, "highest_bid": 95.0}]
        part_prices = [{
            "slug": "test_part",
            "lowest_price": 30.0,
            "highest_bid": 20.0,
            "quantity_in_set": 2,
        }]
        detailed_sets = [{
            "id": "test_set",
            "slug": "test_set",
            "name": "Test Set",
            "setParts": [
                {"code": "test_part", "name": "Test Part", "quantityInSet": 2},
            ],
        }]

        result = calculate_profit_margins(set_prices, part_prices, detailed_sets)
        assert len(result) == 1

        # Instant: sell set to bid (95), buy parts at ask (30*2)
        assert result[0].set_price == pytest.approx(95.0)
        assert result[0].part_cost == pytest.approx(60.0)
        assert result[0].profit_margin == pytest.approx(35.0)

        # Patient: sell set at ask (120), buy parts at bid (20*2)
        assert result[0].patient_set_price == pytest.approx(120.0)
        assert result[0].patient_part_cost == pytest.approx(40.0)
        assert result[0].patient_profit_margin == pytest.approx(80.0)

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
        set_prices = [{"slug": "losing_set", "lowest_price": 55.0, "highest_bid": 50.0}]
        part_prices = [
            {"slug": "expensive_part", "lowest_price": 30.0, "highest_bid": 28.0, "quantity_in_set": 2},
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
        # Instant revenue: highest bid 50 -> margin = -10
        assert result[0].profit_margin == pytest.approx(-10.0)
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
            assert 'instant_profit_margin' in item
            assert 'patient_profit_margin' in item
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
            assert pyd.instant_profit_margin == dct['instant_profit_margin']
            assert pyd.patient_profit_margin == dct['patient_profit_margin']
