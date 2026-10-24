"""Fictional outsider research: validates methodology, NOT real racing skill."""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import pytest

from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from horse_racing_predictions.odds_free_outsider_eval import (
    evaluate_independent_outsider_chronologically,
)


def _raw():
    rows = []
    for race in range(18):
        when = (date(2022, 6, 1) + timedelta(days=race)).isoformat()
        for horse in range(1, 7):
            rows.append({
                "race_id": f"FICTION-{race:02d}",
                "race_date": when,
                "horse_name": f"架空馬{horse}",
                "finish_position": (horse + race) % 6 + 1,
                "distance_m": 1200 + (race % 3) * 400,
                "post_position": horse,
                "age": 3 + (horse % 4),
                "carried_weight": 51 + (horse % 4),
                "racecourse": "Fictional-A" if race % 2 else "Fictional-B",
                "surface": "turf" if race % 2 else "dirt",
                "win_odds": float(2 * horse + race),
                "popularity": 7 - horse,
            })
    return pd.DataFrame(rows)


def _report(raw=None):
    sample = prepare_strict_odds_free_training_sample(
        _raw() if raw is None else raw,
        train_start="2022-06-01", train_end="2022-06-18",
    )
    return evaluate_independent_outsider_chronologically(
        sample,
        fit_through="2022-06-10",
        validation_from="2022-06-11",
        validation_through="2022-06-18",
    )


def test_separate_podium_model_is_fitted_and_only_research():
    result = _report()
    assert result.trainingRaces == 10
    assert result.validationRaces == 8
    assert result.winnerModelTarget == "is_winner"
    assert result.outsiderModelTarget == "finish_position_le_3_train_only"
    assert result.status == "RESEARCH_ONLY_NOT_FROZEN_NOT_PUBLISHABLE"
    assert result.modelSelectionIndependentOfOdds is True
    assert result.independentModelPublicationProven is False
    assert result.publicationAuthorized is False
    assert result.positiveExpectedValueDemonstrated is False
    for metric in (
        result.candidateHitTopThreeRate,
        result.baselineFourthRankHitTopThreeRate,
    ):
        assert 0 <= metric <= 1
    assert result.improvementOverFourthRank == pytest.approx(
        result.candidateHitTopThreeRate -
        result.baselineFourthRankHitTopThreeRate
    )


def test_odds_and_popularity_perturbations_do_not_change_outsider_result():
    original = _raw()
    changed = original.copy()
    changed["win_odds"] = [-100, 999, 0, 5, 2, None] * 18
    changed["popularity"] = [6, 5, 4, 3, 2, 1] * 18
    assert _report(original) == _report(changed)
    assert _report(original) == _report(
        original.drop(columns=["win_odds", "popularity"])
    )


def test_outsider_rejects_2025_2026_final_holdout():
    sample = prepare_strict_odds_free_training_sample(
        _raw(), train_start="2022-06-01", train_end="2022-06-18"
    )
    with pytest.raises(ValueError, match="protected final holdout"):
        evaluate_independent_outsider_chronologically(
            replace(sample, cutoff="2025-01-01"),
            fit_through="2022-06-10",
            validation_from="2022-06-11",
            validation_through="2022-06-18",
        )
    with pytest.raises(ValueError, match="protected final holdout"):
        evaluate_independent_outsider_chronologically(
            sample, fit_through="2022-06-10",
            validation_from="2025-01-01", validation_through="2025-01-10",
        )


def test_outsider_rejects_untrusted_model_features_and_result_columns():
    sample = prepare_strict_odds_free_training_sample(
        _raw(), train_start="2022-06-01", train_end="2022-06-18"
    )
    for leaked in ("finish_position", "win_odds", "popularity", "unknown_signal"):
        with pytest.raises(ValueError, match="leakage|unrecognized"):
            evaluate_independent_outsider_chronologically(
                replace(sample, features=sample.features + (leaked,)),
                fit_through="2022-06-10",
                validation_from="2022-06-11",
                validation_through="2022-06-18",
            )


def test_outsider_rejects_inconsistent_validation_winner_label():
    sample = prepare_strict_odds_free_training_sample(
        _raw(), train_start="2022-06-01", train_end="2022-06-18"
    )
    changed = sample.frame.copy()
    target = changed.index[changed["race_id"].eq("FICTION-14")][0]
    changed.loc[target, "is_winner"] = 1 - int(changed.loc[target, "is_winner"])
    with pytest.raises(ValueError, match="inconsistent"):
        evaluate_independent_outsider_chronologically(
            replace(sample, frame=changed),
            fit_through="2022-06-10",
            validation_from="2022-06-11",
            validation_through="2022-06-18",
        )


def test_outsider_fitting_and_validation_must_not_overlap():
    sample = prepare_strict_odds_free_training_sample(
        _raw(), train_start="2022-06-01", train_end="2022-06-18"
    )
    with pytest.raises(ValueError, match="protected final holdout"):
        evaluate_independent_outsider_chronologically(
            sample, fit_through="2022-06-15",
            validation_from="2022-06-11",
            validation_through="2022-06-18",
        )


def test_outsider_never_reads_validation_results_as_model_features(monkeypatch):
    from horse_racing_predictions import odds_free_outsider_eval as module
    original = module.BaselineProbabilityModel.predict_win_probability
    observed = []

    def checked(self, frame, race_col="race_id"):
        assert "finish_position" not in frame
        assert "is_winner" not in frame
        assert "win_odds" not in frame
        observed.append(tuple(self.feature_columns))
        return original(self, frame, race_col=race_col)

    monkeypatch.setattr(module.BaselineProbabilityModel, "predict_win_probability", checked)
    result = _report()
    assert result.validationRaces == 8
    assert len(observed) == 2
    assert observed[0] == observed[1]
