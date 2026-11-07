"""Friday-before-draw feature availability tests: fictional horses only."""
from __future__ import annotations

from dataclasses import replace

import pytest

from horse_racing_predictions.friday_feature_projection import (
    project_friday_research_features,
)
from horse_racing_predictions.friday_predraw_features import (
    assert_friday_predraw_feature_list,
    select_friday_predraw_research_features,
)
from test_strict_dual_catboost_candidate import _history, _sample


def test_friday_starter_weights_weather_track_draw_and_final_field_excluded():
    historic = _history()
    historic["horse_weight"] = [460 + x % 20 for x in range(len(historic))]
    historic["horse_weight_delta"] = [x % 4 for x in range(len(historic))]
    historic["weather"] = "sunny"
    historic["track_condition"] = "firm"
    sample = _sample(historic)
    filtered, report = project_friday_research_features(sample)
    forbidden = {
        "post_position", "relative_post_position",
        "horse_weight", "horse_weight_delta", "horse_weight_vs_race_mean",
        "weather", "track_condition", "field_size",
        "carried_weight", "carried_weight_vs_race_mean",
    }
    assert forbidden.issubset(set(sample.features))
    assert set(filtered.features).isdisjoint(forbidden)
    assert report.friday_feature_count == len(filtered.features)
    assert report.original_feature_count == len(sample.features)
    assert report.research_only is True
    assert report.friday_roster_independently_verified is False
    assert report.publication_authorized is False
    assert report.positive_expected_value_demonstrated is False
    assert_friday_predraw_feature_list(filtered.features)
    # The old caller path and new projection must never drift apart.
    assert select_friday_predraw_research_features(sample).features == filtered.features


@pytest.mark.parametrize("unavailable", [
    "post_position", "weather", "track_condition", "horse_weight",
    "carried_weight", "field_size", "relative_post_position",
    "horse_weight_vs_race_mean", "horse_recent_future_finish",
])
def test_friday_preview_rejects_unavailable_feature_name(unavailable):
    with pytest.raises(ValueError, match="Friday model|unrecognized"):
        assert_friday_predraw_feature_list(("age", unavailable))


def test_friday_projection_refuses_protected_cutoff_and_preserves_source():
    sample = _sample()
    original_columns = sample.features
    projected, _ = project_friday_research_features(sample)
    assert sample.features == original_columns
    assert projected.frame is not sample.frame
    assert set(projected.features).issubset(set(sample.features))
    with pytest.raises(ValueError, match="PROTECTED_FINAL_HOLDOUT"):
        project_friday_research_features(replace(sample, cutoff="2025-01-01"))


def test_a_preverified_safe_only_list_does_not_require_exclusion():
    sample = _sample()
    filtered, _ = project_friday_research_features(sample)
    again, report = project_friday_research_features(filtered)
    assert again.features == filtered.features
    assert report.excluded_features == ()
    assert_friday_predraw_feature_list(again.features)


def test_fitted_friday_research_candidate_cannot_use_race_day_features():
    pytest.importorskip("catboost")
    from horse_racing_predictions.strict_dual_catboost_candidate import (
        fit_strict_dual_catboost_candidate,
    )
    sample = select_friday_predraw_research_features(_sample())
    candidate = fit_strict_dual_catboost_candidate(
        sample, fit_through="2022-06-10",
        validation_from="2022-06-11", validation_through="2022-06-18",
        iterations=30,
    )
    assert candidate.features == sample.features
    assert "field_size" not in candidate.features
    assert "carried_weight" not in candidate.features
    assert "post_position" not in candidate.features
    assert candidate.metrics.publicationAuthorized is False
