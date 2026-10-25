"""Fictional JRA Friday prior-to-draw native dual model regressions."""
from __future__ import annotations

from datetime import datetime

import pytest

from horse_racing_predictions.dual_candidate_private_preview import (
    load_dual_research_candidate,
)
from horse_racing_predictions.friday_predraw_features import (
    select_friday_predraw_research_features,
    assert_friday_predraw_feature_list,
)
from horse_racing_predictions.friday_predraw_dual_preview import (
    private_friday_predraw_dual_preview,
)
from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from horse_racing_predictions.strict_dual_catboost_candidate import (
    fit_strict_dual_catboost_candidate,
    save_dual_candidate_for_research,
)
from test_strict_dual_catboost_candidate import _history
from test_dual_candidate_private_preview import _fake_recent_and_entries

FRIDAY = datetime.fromisoformat("2026-10-30T20:00:00+09:00")


def _trained_predraw(tmp_path):
    pytest.importorskip("catboost")
    sample = prepare_strict_odds_free_training_sample(
        _history(), train_start="2022-06-01", train_end="2022-06-18",
    )
    sample = select_friday_predraw_research_features(sample)
    assert "post_position" not in sample.features
    assert "relative_post_position" not in sample.features
    assert "weather" not in sample.features
    assert "horse_weight" not in sample.features
    candidate = fit_strict_dual_catboost_candidate(
        sample, fit_through="2022-06-10",
        validation_from="2022-06-11",
        validation_through="2022-06-18", iterations=30,
    )
    path = tmp_path / "friday-predraw-models"
    save_dual_candidate_for_research(
        candidate, destination=path, source_ref="fictional-friday-not-real",
    )
    return load_dual_research_candidate(path)


def test_true_friday_predraw_top3_outsider_without_horse_numbers(tmp_path):
    loaded = _trained_predraw(tmp_path)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    result = private_friday_predraw_dual_preview(
        loaded, history=history, entries=entries,
        expected_race_ids=ids, race_date="2026-11-01",
        observed_at=FRIDAY,
    )
    assert result["raceCount"] == 24
    assert result["runnerCount"] == 144
    assert result["realWinAndOutsiderModelsComputed"] is True
    assert result["raceNumbersKnownOrInvented"] is False
    assert len(result["winModelOutputSha256"]) == 64
    assert len(result["outsiderSelectionSha256"]) == 64
    assert result["publicationAuthorized"] is False
    assert result["sourceRightsIndependentlyVerified"] is False
    assert result["upstreamOddsIndependentSourceProven"] is False
    assert result["positiveExpectedValueDemonstrated"] is False
    assert "races" not in result


def test_friday_declared_runner_counts_must_match_entire_card(tmp_path):
    loaded = _trained_predraw(tmp_path)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    exact_counts = {rid: 6 for rid in ids}
    result = private_friday_predraw_dual_preview(
        loaded, history=history, entries=entries,
        expected_race_ids=ids, race_date="2026-11-01",
        observed_at=FRIDAY, expected_runner_counts=exact_counts,
    )
    assert result["callerDeclaredRunnerCountsChecked"] is True
    assert result["officialRosterCountIndependentlyVerified"] is False
    assert result["publicationAuthorized"] is False


def test_friday_model_explicitly_rejects_unavailable_draw_features(tmp_path):
    from test_dual_candidate_private_preview import _artifact
    default_loaded = load_dual_research_candidate(_artifact(tmp_path))
    with pytest.raises(ValueError, match="Friday model"):
        assert_friday_predraw_feature_list(default_loaded.features)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    with pytest.raises(ValueError, match="Friday model"):
        private_friday_predraw_dual_preview(
            default_loaded, history=history, entries=entries,
            expected_race_ids=ids, race_date="2026-11-01",
            observed_at=FRIDAY,
        )


def test_friday_date_immutable_no_sunday_after_result_retroactive(tmp_path):
    loaded = _trained_predraw(tmp_path)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    for date in (
        "2026-10-29T20:00:00+09:00",
        "2026-10-31T00:00:00+09:00",
        "2026-11-01T07:00:00+09:00",
    ):
        with pytest.raises(ValueError, match="Friday-only"):
            private_friday_predraw_dual_preview(
                loaded, history=history, entries=entries,
                expected_race_ids=ids, race_date="2026-11-01",
                observed_at=datetime.fromisoformat(date),
            )


def test_friday_cannot_assume_early_announced_roster_complete(tmp_path):
    loaded = _trained_predraw(tmp_path)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    removed = entries.iloc[:-1].copy()
    counts = {rid: 6 for rid in ids}
    with pytest.raises(ValueError, match="incomplete Friday roster"):
        private_friday_predraw_dual_preview(
            loaded, history=history, entries=removed,
            expected_race_ids=ids, race_date="2026-11-01",
            observed_at=FRIDAY, expected_runner_counts=counts,
        )


def test_friday_market_odds_never_enter_model_or_roster(tmp_path):
    loaded = _trained_predraw(tmp_path)
    history, entries, ids = _fake_recent_and_entries()
    entries = entries.drop(columns=["post_position"])
    entries["popularity"] = 1
    with pytest.raises(ValueError, match="market or outcome"):
        private_friday_predraw_dual_preview(
            loaded, history=history, entries=entries,
            expected_race_ids=ids, race_date="2026-11-01",
            observed_at=FRIDAY,
        )
