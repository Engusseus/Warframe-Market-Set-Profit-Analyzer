"""Unit tests for data normalization utilities."""
import pytest

from app.core.normalization import normalize_data


class TestNormalizeData:
    """Tests for normalize_data function."""

    @pytest.mark.unit
    def test_normalizes_to_zero_one_range(self):
        """Test that values are normalized to 0-1 range."""
        values = [10, 20, 30, 40, 50]
        result = normalize_data(values)

        assert len(result) == len(values)
        assert min(result) == 0.0
        assert max(result) == 1.0

    @pytest.mark.unit
    def test_preserves_relative_ordering(self):
        """Test that relative ordering is preserved."""
        values = [10, 30, 20, 50, 40]
        result = normalize_data(values)

        # Original order of indices by value: 0 < 2 < 1 < 4 < 3
        # Normalized should maintain: result[0] < result[2] < result[1] < result[4] < result[3]
        assert result[0] < result[2] < result[1] < result[4] < result[3]

    @pytest.mark.unit
    def test_empty_list_returns_empty(self):
        """Test that empty input returns empty output."""
        result = normalize_data([])
        assert result == []

    @pytest.mark.unit
    def test_single_value_returns_zero(self):
        """Test that single value returns zero (no range)."""
        result = normalize_data([42.0])
        assert result == [0.0]

    @pytest.mark.unit
    def test_all_same_values_returns_zeros(self):
        """Test that identical values return zeros."""
        values = [5.0, 5.0, 5.0, 5.0]
        result = normalize_data(values)
        assert result == [0.0, 0.0, 0.0, 0.0]

    @pytest.mark.unit
    def test_handles_negative_values(self):
        """Test that negative values are handled correctly."""
        values = [-10, 0, 10, 20]
        result = normalize_data(values)

        assert min(result) == 0.0
        assert max(result) == 1.0
        # Check proportional values
        assert result[0] == 0.0   # -10 is min
        assert result[3] == 1.0   # 20 is max
        assert result[1] == pytest.approx(1/3)  # 0 is 1/3 of range
        assert result[2] == pytest.approx(2/3)  # 10 is 2/3 of range

    @pytest.mark.unit
    def test_handles_float_values(self):
        """Test that float values are handled correctly."""
        values = [0.1, 0.5, 0.9]
        result = normalize_data(values)

        assert result[0] == 0.0
        assert result[2] == 1.0
        assert result[1] == 0.5

    @pytest.mark.unit
    def test_custom_min_max(self):
        """Test that custom min/max values can be provided."""
        values = [20, 30, 40]
        result = normalize_data(values, min_val=0, max_val=100)

        # Values should be normalized relative to 0-100 range
        assert result[0] == 0.2  # 20/100
        assert result[1] == 0.3  # 30/100
        assert result[2] == 0.4  # 40/100

    @pytest.mark.unit
    def test_custom_min_equal_to_max_returns_zeros(self):
        """Test that custom min equal to max returns zeros."""
        values = [50, 50, 50]
        result = normalize_data(values, min_val=50, max_val=50)
        assert result == [0.0, 0.0, 0.0]

    @pytest.mark.unit
    def test_large_range(self):
        """Test normalization with large value range."""
        values = [0, 1000000, 500000]
        result = normalize_data(values)

        assert result[0] == 0.0
        assert result[1] == 1.0
        assert result[2] == 0.5

    @pytest.mark.unit
    def test_very_small_range(self):
        """Test normalization with very small value range."""
        values = [1.0000001, 1.0000002, 1.0000003]
        result = normalize_data(values)

        assert result[0] == 0.0
        assert result[2] == 1.0
        # Middle value should be approximately 0.5
        assert result[1] == pytest.approx(0.5, rel=0.01)
