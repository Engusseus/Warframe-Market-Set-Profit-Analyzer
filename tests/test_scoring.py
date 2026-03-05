from wf_market_analyzer import PriceData, ResultRow, SetData, VolumeData, score_results


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
