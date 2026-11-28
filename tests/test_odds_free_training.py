"""Strict odds-free research sampling invariance: no market-based eligibility."""
from __future__ import annotations

import pandas as pd
import pytest

from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)


def _history():
    rows = []
    for date, suffix in (("2021-06-12", "A"), ("2021-07-10", "B")):
        for number in range(1, 5):
            rows.append({
                "race_id": f"JRA-{suffix}",
                "race_date": date,
                "horse_name": f"架空履歴馬{number}",
                "finish_position": number,
                "distance_m": 1600,
                "surface": "turf",
                "racecourse": "Tokyo",
                "win_odds": None if number == 2 else 1.0 + number,
                "market_popularity": 5 - number,
            })
    return pd.DataFrame(rows)


def _sample(frame):
    return prepare_strict_odds_free_training_sample(
        frame, train_start="2021-06-01", train_end="2021-07-31"
    )


def test_missing_odds_does_not_filter_valid_runners():
    sample = _sample(_history())
    assert sample.runner_count == 8
    assert sample.race_count == 2
    assert "win_odds" in sample.market_columns_excluded
    assert "market_popularity" in sample.market_columns_excluded
    assert "win_odds" not in sample.frame.columns
    assert "market_popularity" not in sample.frame.columns
    assert "finish_position" not in sample.features
    assert "horse_recent_top3_rate_3" in sample.features


def test_model_sample_and_features_invariant_to_any_odds_or_popularity_values():
    original = _history()
    baseline = _sample(original)
    modified = original.copy()
    modified["win_odds"] = [-1, None, 0, 10_000] * 2
    modified["market_popularity"] = [100, 1, 2, 3] * 2
    altered = _sample(modified)
    without_markets = _sample(original.drop(columns=[
        "win_odds", "market_popularity"
    ]))
    pd.testing.assert_frame_equal(baseline.frame, altered.frame)
    pd.testing.assert_frame_equal(baseline.frame, without_markets.frame)
    assert baseline.features == altered.features == without_markets.features


@pytest.mark.parametrize("patch", [
    lambda f: f.assign(race_date="2026-10-24"),
    lambda f: f.assign(finish_position=0),
    lambda f: f.assign(finish_position=None),
    lambda f: f.assign(horse_name=""),
    lambda f: f.assign(finish_position=2),
])
def test_unusable_or_post_holdout_history_fails(patch):
    with pytest.raises(ValueError):
        _sample(patch(_history()))


def test_protected_holdout_rows_block_even_with_training_end_2021():
    data = _history()
    future = data.iloc[[0]].copy()
    future["race_date"] = "2025-01-01"
    future["race_id"] = "PROTECTED"
    with pytest.raises(ValueError, match="protected"):
        _sample(pd.concat([data, future], ignore_index=True))


def test_duplicate_starter_and_multiple_winners_fail():
    raw = _history()
    with pytest.raises(ValueError, match="duplicate"):
        _sample(pd.concat([raw, raw.iloc[[0]]], ignore_index=True))
    wrong = raw.copy()
    wrong.loc[1, "finish_position"] = 1
    with pytest.raises(ValueError, match="exactly one winner"):
        _sample(wrong)


def test_research_training_cutoff_must_precede_final_holdout():
    with pytest.raises(ValueError, match="protected"):
        prepare_strict_odds_free_training_sample(
            _history(), train_start="2020-01-01", train_end="2025-01-01"
        )


def test_market_alias_column_never_enters_feature_builder():
    data = _history()
    data["単勝"] = ["999"] * len(data)
    sample = _sample(data)
    assert "単勝" in sample.market_columns_excluded
    assert "単勝" not in sample.frame.columns


def test_no_training_or_model_promotion_happens_during_sample_preparation():
    result = _sample(_history())
    assert result.runner_count == len(_history())
    assert not hasattr(result, "model")
    assert not hasattr(result, "publicationAuthorized")
