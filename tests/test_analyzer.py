import pytest

import wf_market_analyzer as wfa

# Helper to create dataclasses easily
SetData = wfa.SetData
PriceData = wfa.PriceData
VolumeData = wfa.VolumeData
ResultData = wfa.ResultData
SetProfitAnalyzer = wfa.SetProfitAnalyzer


def test_calculate_average_price_sell():
    analyzer = SetProfitAnalyzer()
    orders = [
        {'order_type': 'sell', 'platinum': 10},
        {'order_type': 'sell', 'platinum': 8},
        {'order_type': 'sell', 'platinum': 12},
        {'order_type': 'buy', 'platinum': 9},
    ]
    avg = analyzer.calculate_average_price(orders, 'sell', count=2)
    assert avg == pytest.approx((8 + 10) / 2)


def test_calculate_average_price_buy_with_adjusted_count():
    analyzer = SetProfitAnalyzer()
    orders = [
        {'order_type': 'buy', 'platinum': 20},
        {'order_type': 'buy', 'platinum': 30},
    ]
    avg = analyzer.calculate_average_price(orders, 'buy', count=5)
    assert avg == pytest.approx((30 + 20) / 2)


def test_calculate_median_price_sell(monkeypatch):
    monkeypatch.setattr(wfa, 'np', __import__('numpy'), raising=False)
    analyzer = SetProfitAnalyzer()
    orders = [
        {'order_type': 'sell', 'platinum': 10},
        {'order_type': 'sell', 'platinum': 8},
        {'order_type': 'sell', 'platinum': 12},
    ]
    median = analyzer.calculate_median_price(orders, 'sell', count=2)
    assert median == pytest.approx(9.0)


def test_calculate_median_price_buy(monkeypatch):
    monkeypatch.setattr(wfa, 'np', __import__('numpy'), raising=False)
    analyzer = SetProfitAnalyzer()
    orders = [
        {'order_type': 'buy', 'platinum': 7},
        {'order_type': 'buy', 'platinum': 9},
    ]
    median = analyzer.calculate_median_price(orders, 'buy', count=2)
    assert median == pytest.approx(8.0)


def test_normalize_data_scores():
    analyzer = SetProfitAnalyzer()
    results = [
        ResultData(
            set_data=SetData(slug='a', name='A', parts={}, part_names={}),
            price_data=PriceData(set_price=0, part_prices={}, total_part_cost=90, profit=10, profit_margin=0.1),
            volume_data=VolumeData(volume_48h=100),
            score=0,
        ),
        ResultData(
            set_data=SetData(slug='b', name='B', parts={}, part_names={}),
            price_data=PriceData(set_price=0, part_prices={}, total_part_cost=80, profit=20, profit_margin=0.2),
            volume_data=VolumeData(volume_48h=200),
            score=0,
        ),
        ResultData(
            set_data=SetData(slug='c', name='C', parts={}, part_names={}),
            price_data=PriceData(set_price=0, part_prices={}, total_part_cost=70, profit=30, profit_margin=0.3),
            volume_data=VolumeData(volume_48h=300),
            score=0,
        ),
    ]
    normalized = analyzer.normalize_data(results)
    scores = [r.score for r in normalized]
    assert scores == pytest.approx([0.0, 1.1, 2.2])
