"""Entirely fictional local folds: assertions are regression tests, not skill scores."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
import json

import pandas as pd
import pytest

from horse_racing_predictions.odds_free_chronological_eval import (
    evaluate_strict_odds_free_chronologically,
)
from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)


def _race_history():
    rows = []
    beginning = date(2021, 6, 1)
    for race_i in range(15):
        day = (beginning + timedelta(days=race_i)).isoformat()
        for horse_i in range(1, 5):
            rows.append({
                "race_id": f"FICTIONAL-{race_i:03d}",
                "race_date": day,
                "horse_name": f"架空馬{horse_i}",
                "finish_position": (horse_i + race_i) % 4 + 1,
                "distance_m": 1200 + 200 * (race_i % 4),
                "racecourse": "Fictional-A" if race_i % 2 else "Fictional-B",
                "surface": "turf" if race_i % 3 else "dirt",
                "age": 3 + horse_i % 3,
                "carried_weight": 51 + (horse_i % 4),
                "win_odds": 2 + horse_i + race_i,
                "popularity": 4 - horse_i,
            })
    return pd.DataFrame(rows)


def _sample(raw=None):
    return prepare_strict_odds_free_training_sample(
        _race_history() if raw is None else raw,
        train_start="2021-06-01",
        train_end="2021-06-15",
    )


def _eval(sample):
    return evaluate_strict_odds_free_chronologically(
        sample,
        fit_through="2021-06-09",
        validation_from="2021-06-10",
        validation_through="2021-06-15",
    )


def test_pre_holdout_real_pipeline_measures_metrics_not_released():
    result = _eval(_sample())
    assert result.status == "RESEARCH_VALIDATED_NOT_RELEASED"
    assert result.trainingRaces == 9
    assert result.validationRaces == 6
    assert result.trainingRunners == 36
    assert result.validationRunners == 24
    assert result.featureCount > 3
    assert result.publicationAuthorized is False
    assert result.positiveExpectedValueDemonstrated is False
    for field in ("top1Accuracy", "top3Coverage",
                  "orderedTop3Accuracy", "predictedRankFourTop3Rate",
                  "brierRunner", "uniformTop1Reference"):
        assert 0 <= getattr(result, field) <= 1
    assert result.winnerLogLoss >= 0
    assert result.uniformTop1Reference == 0.25
    assert result.top1Accuracy >= 0
    assert "RESEARCH" in json.dumps(result.__dict__)


def test_odds_and_popularity_changes_cannot_affect_metrics_or_samples():
    history = _race_history()
    first = _eval(_sample(history))
    mutated = history.copy()
    mutated["win_odds"] = [None, 0, 10_000, -3] * 15
    mutated["popularity"] = [9, 10, 1, 0] * 15
    changed = _eval(_sample(mutated))
    removed = _eval(_sample(history.drop(columns=["win_odds", "popularity"])))
    assert first == changed == removed


def test_training_and_validation_must_use_disjoint_dates():
    sample = _sample()
    with pytest.raises(ValueError, match="follow fitting"):
        evaluate_strict_odds_free_chronologically(
            sample, fit_through="2021-06-12",
            validation_from="2021-06-10",
            validation_through="2021-06-15",
        )


def test_final_holdout_cannot_be_included_by_overriding_sample_metadata():
    sample = _sample()
    future = replace(sample, cutoff="2026-01-01")
    with pytest.raises(ValueError, match="protected final holdout"):
        _eval(future)
    with pytest.raises(ValueError, match="exclude final holdout"):
        evaluate_strict_odds_free_chronologically(
            sample, fit_through="2021-06-09",
            validation_from="2026-10-01",
            validation_through="2026-10-31",
        )


def test_too_few_training_races_block_model_fit():
    sample = _sample()
    with pytest.raises(ValueError, match="insufficient"):
        evaluate_strict_odds_free_chronologically(
            sample, fit_through="2021-06-05",
            validation_from="2021-06-11",
            validation_through="2021-06-12",
        )


def test_caller_cannot_disable_minimum_fold_size_checks():
    with pytest.raises(ValueError, match="minimum fold sizes"):
        evaluate_strict_odds_free_chronologically(
            _sample(), fit_through="2021-06-09",
            validation_from="2021-06-10",
            validation_through="2021-06-15",
            minimum_training_races=1, minimum_validation_races=1,
        )


def test_validation_podium_tie_or_missing_second_blocks_metrics():
    sample = _sample()
    tampered = sample.frame.copy()
    mask = (tampered["race_id"] == "FICTIONAL-010") & tampered["finish_position"].eq(2)
    assert mask.any()
    tampered.loc[mask, "finish_position"] = 3
    with pytest.raises(ValueError, match="podium ranks"):
        _eval(replace(sample, frame=tampered))


def test_fake_market_column_after_preparation_blocks():
    sample = _sample()
    tampered = sample.frame.copy()
    tampered["market_rank"] = 1
    with pytest.raises(ValueError, match="market column"):
        _eval(replace(sample, frame=tampered))


def test_model_does_not_claim_expected_value_without_valid_pre_race_odds():
    result = _eval(_sample())
    assert result.positiveExpectedValueDemonstrated is False
    assert "ROI" not in result.__dict__
    assert "win_odds" not in result.__dict__



@pytest.mark.parametrize("leaked", [
    "finish_position", "is_winner", "last_3f", "corner_4",
    "race_date", "race_id", "prize_money",
    "unknown_future_finish", "win_odds", "popularity",
])
def test_cannot_inject_actual_outcomes_or_unapproved_features(leaked):
    sample = _sample()
    # Model payload might be constructed by other callers. Even when it
    # contains perfectly predictive label information, the public metrics
    # must fail rather than show an artificially impressive result.
    bad = replace(sample, features=sample.features + (leaked,))
    with pytest.raises(ValueError, match="leakage|unrecognized"):
        _eval(bad)


def test_duplicate_model_feature_names_are_not_accepted():
    sample = _sample()
    bad = replace(sample, features=sample.features + (sample.features[0],))
    with pytest.raises(ValueError, match="duplicate"):
        _eval(bad)


def test_claimed_winner_label_must_match_actual_finish_rank():
    sample = _sample()
    tampered = sample.frame.copy()
    target = tampered.index[tampered["race_id"].eq("FICTIONAL-012")][0]
    tampered.loc[target, "is_winner"] = 1 - int(tampered.loc[target, "is_winner"])
    with pytest.raises(ValueError, match="inconsistent"):
        _eval(replace(sample, frame=tampered))


def test_out_of_field_ranks_and_noninteger_ranks_are_rejected():
    sample = _sample()
    for invalid in (0, 2.5, 99):
        bad = sample.frame.copy()
        row = bad.index[bad["race_id"].eq("FICTIONAL-010") &
                        bad["finish_position"].eq(4)][0]
        bad.loc[row, "finish_position"] = invalid
        with pytest.raises(ValueError, match="valid ranks"):
            _eval(replace(sample, frame=bad))


def test_forecast_day_feature_independent_of_its_own_finished_result():
    # This only checks the existing feature builder's point-in-time use;
    # later days may legitimately use earlier races' results.
    original = _race_history()
    sample = _sample(original)
    altered = original.copy()
    target_day = "2021-06-13"
    altered.loc[altered["race_date"].eq(target_day), "finish_position"] = [4, 3, 2, 1]
    changed = _sample(altered)
    pre = sample.frame.loc[
        sample.frame["race_date"].eq(pd.Timestamp(target_day)),
        list(sample.features),
    ].reset_index(drop=True)
    post = changed.frame.loc[
        changed.frame["race_date"].eq(pd.Timestamp(target_day)),
        list(sample.features),
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(pre, post)
