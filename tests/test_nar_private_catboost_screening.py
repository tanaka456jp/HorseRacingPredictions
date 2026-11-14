"""Synthetic-only NAR dual-model screening and sealed-holdout checks."""
from dataclasses import replace

import pytest

from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_prior_day_features import (
    NarAsOfFeatures, NarAsOfResearchBatch, NarResearchTarget,
)
from horse_racing_predictions.nar_private_catboost_screening import (
    _FEATURES, _project_only_fit_and_tune, fit_nar_private_catboost_screening,
)


def _fictional_batch() -> NarAsOfResearchBatch:
    dates = [
        "2017-03-01", "2018-04-01", "2019-05-01",
        "2020-06-01", "2021-07-01",
        "2022-03-01", "2022-05-01", "2022-07-01",
        "2023-08-01", "2024-09-01",
    ]
    rows = []
    for r, day in enumerate(dates):
        for num in range(1, 9):
            # Fabricated form observations; the rank label is independent
            # of the model features except for the intentionally learnable
            # synthetic relationship; no real racing data are accessed.
            rank = (num + r * 3 - 1) % 8 + 1
            rows.append(NarResearchTarget(
                race_key=("架空競馬場", day.replace("-", ""), 3),
                horse_key=(f"架空馬{num}", f"2015{num:02d}01"),
                horse_number=num, race_day=day, surface="ダート",
                distance_m=1600,
                asof=NarAsOfFeatures(
                    prior_starts=r,
                    prior_wins=int(num == 1) * min(r, 2),
                    prior_top3=min(r, 3) if num <= 3 else 0,
                    prior_win_rate=(int(num == 1) * min(r, 2) / r if r else 0.0),
                    prior_top3_rate=(min(r, 3) / r if r and num <= 3 else 0.0),
                    prior_mean_finish=(float(num) if r else None),
                    days_since_prior_start=(28 if r else None),
                ),
                final_finish_label=rank,
            ))
    return NarAsOfResearchBatch(
        status="NAR_RETROSPECTIVE_PRIOR_DAY_FEATURES_NO_PREOFF_PROOF",
        eligible_races=len(dates),
        target_runner_rows=len(rows),
        first_year=2017, last_year=2024, return_data=tuple(rows),
    )


def test_projection_never_reads_sealed_holdout_labels():
    batch = _fictional_batch()
    sealed = tuple(
        replace(row, final_finish_label=None)
        if row.race_day >= "2023-01-01" else row
        for row in batch.return_data
    )
    projected, sealed_races = _project_only_fit_and_tune(
        replace(batch, return_data=sealed),
    )
    assert len(projected) == 64
    assert sealed_races == 2
    assert projected["race_day"].max().isoformat() == "2022-07-01"
    assert set(_FEATURES).issubset(projected.columns)
    assert "popularity" not in projected.columns
    assert "odds" not in projected.columns
    assert "finish_time" not in projected.columns
    assert "__finish_label" not in _FEATURES
    assert "horse_key" not in projected.columns
    assert "race_key" not in projected.columns


def test_holdout_dates_cannot_be_moved_into_training():
    batch = _fictional_batch()
    protected = replace(
        batch.return_data[-1],
        race_day="2025-09-01",
    )
    changed = replace(
        batch, return_data=batch.return_data[:-1] + (protected,),
    )
    with pytest.raises(UnsafeNarSource, match="NAR_SCREENING_PROTECTED_OR_UNEXPECTED_PERIOD"):
        _project_only_fit_and_tune(changed)


def test_malformed_asof_counts_block_model_screening():
    batch = _fictional_batch()
    invalid = replace(batch.return_data[0], asof=replace(
        batch.return_data[0].asof,
        prior_starts=0, prior_wins=1,
    ))
    changed = replace(batch, return_data=(invalid,) + batch.return_data[1:])
    with pytest.raises(UnsafeNarSource, match="NAR_SCREENING_ASOF_FEATURE_INVALID"):
        _project_only_fit_and_tune(changed)


def test_duplicate_runner_refused_without_leaking_source():
    batch = _fictional_batch()
    changed = replace(
        batch, return_data=batch.return_data + (batch.return_data[-1],),
        target_runner_rows=batch.target_runner_rows + 1,
    )
    with pytest.raises(UnsafeNarSource, match="NAR_SCREENING_DUPLICATE_RUNNER"):
        _project_only_fit_and_tune(changed)


def test_fictional_catboost_winner_podium_independently_fit():
    pytest.importorskip("catboost")
    batch = _fictional_batch()
    candidate = fit_nar_private_catboost_screening(batch, iterations=30)
    m = candidate.metrics
    assert m.status == "NAR_2022_MODEL_SELECTION_ONLY_SEALED_2023_2024"
    assert m.training_races == 5
    assert m.tuning_races == 3
    assert m.sealed_races_unscored == 2
    assert m.training_runners == 40
    assert m.tuning_runners == 24
    assert m.independent_models_fitted
    assert candidate.winner.model is not candidate.outsider.model
    assert 0 <= m.winner_top1_hit_rate_2022 <= 1
    assert 0 <= m.win_rank_top3_overlap_2022 <= 1
    assert 0 <= m.independent_outsider_podium_hit_rate_2022 <= 1
    assert not m.sealed_holdout_labels_used
    assert not m.used_market_or_popularity
    assert not m.official_returns_evaluated
    assert not m.real_positive_expected_value_proven
    assert not m.public_distribution_authorized
    assert "架空馬" not in repr(candidate)
    assert "架空競馬場" not in repr(candidate)


def test_fictional_catboost_results_unchanged_if_sealed_labels_tampered():
    pytest.importorskip("catboost")
    batch = _fictional_batch()
    baseline = fit_nar_private_catboost_screening(batch, iterations=30)
    changed = replace(batch, return_data=tuple(
        replace(row, final_finish_label=None)
        if row.race_day >= "2023-01-01" else row
        for row in batch.return_data
    ))
    tested = fit_nar_private_catboost_screening(changed, iterations=30)
    assert baseline.metrics == tested.metrics


def test_folds_must_have_independent_sufficient_race_counts():
    batch = _fictional_batch()
    shortened = tuple(
        row for row in batch.return_data
        if row.race_day not in ("2022-05-01", "2022-07-01")
    )
    changed = replace(
        batch, return_data=shortened, target_runner_rows=len(shortened),
    )
    with pytest.raises(UnsafeNarSource, match="NAR_SCREENING_NOT_ENOUGH_RACES"):
        fit_nar_private_catboost_screening(changed, iterations=30)


def test_invalid_iteration_setting_rejected():
    with pytest.raises(UnsafeNarSource, match="NAR_SCREENING_ITERATIONS_INVALID"):
        fit_nar_private_catboost_screening(_fictional_batch(), iterations=0)
