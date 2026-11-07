"""Synthetic, immutable, odds-free forecast to NAR settlement join."""
from datetime import datetime, timezone, timedelta

from horse_racing_predictions.nar_published_result_normalizer import (
    normalize_nar_published_results,
)
from horse_racing_predictions.nar_economic_settlement_adapter import (
    nar_canonical_race_id,
    to_nar_final_settlements,
)
from horse_racing_predictions.oddsfree_ev_research import (
    FrozenOddsFreeForecast, evaluate_frozen_oddsfree_economics,
)
from test_nar_published_result_normalizer import _fixture


def test_nar_result_can_join_previously_frozen_fictional_forecast():
    data = normalize_nar_published_results(_fixture(), month="202402")
    settlements = to_nar_final_settlements(data)
    assert len(settlements) == 1
    settlement = settlements[0]
    identity = nar_canonical_race_id(("架空競馬場", "20240214", 3))
    assert settlement.race_id == identity
    assert settlement.finishing_positions["1"] == 1
    assert settlement.win_return_per_100_yen["1"] == 250
    assert settlement.place_return_per_100_yen["3"] == 130
    assert settlement.place_return_per_100_yen["4"] == 0

    scores = {str(i): float(9-i) for i in range(1, 9)}
    longshots = {str(i): (10.0 if i == 4 else 0.5) for i in range(1, 9)}
    frozen = FrozenOddsFreeForecast(
        race_id=identity,
        race_day="2024-02-14",
        post_time_utc=datetime(2024, 2, 14, 6, 40, tzinfo=timezone.utc),
        predicted_at_utc=datetime(2024, 2, 13, 12, tzinfo=timezone.utc),
        model_ref="FICTIONAL_MODEL_FROZEN",
        model_fit_through_day="2023-12-31",
        winner_scores=scores,
        outsider_scores=longshots,
    )
    result = evaluate_frozen_oddsfree_economics(
        [frozen], list(settlements),
        bootstrap_samples=200,
    )
    assert result.races == 1
    assert result.top1_win_return_yen == 250
    assert result.outsider_place_return_yen == 0
    assert result.combined_stake_yen == 200
    assert result.combined_return_yen == 250
    assert result.combined_realized_roi == 0.25
    assert not result.real_source_rights_verified
    assert not result.positive_expected_value_demonstrated
    assert not result.publication_authorized


def test_settlement_adapter_never_adds_popularity_or_market_scores():
    data = normalize_nar_published_results(_fixture(), month="202402")
    result = to_nar_final_settlements(data)
    for settlement in result:
        assert not hasattr(settlement, "win_odds")
        assert not hasattr(settlement, "popularity")
        assert not hasattr(settlement, "forecast")
