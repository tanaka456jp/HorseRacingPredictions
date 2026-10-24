"""Synthetic Sunday runner exercises actual inference call; never real 2026 data."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from horse_racing_predictions.model_artifact import ChampionManifest, LoadedChampion
from horse_racing_predictions.sunday_ai_research import private_sunday_ai_preview


RACE = "JRA-20261025-KYOTO-11"
AS_OF = datetime.fromisoformat("2026-10-24T16:59:00+09:00")


class FakeFittedModel:
    """Predicts on the existing real feature-building path, not editor text."""

    def predict_win_probability(self, frame, race_col="race_id"):
        assert "distance_m" in frame
        assert frame["finish_position"].isna().all()
        n = len(frame)
        values = list(range(n, 0, -1))
        total = sum(values)
        return pd.Series([w / total for w in values], index=frame.index)


def _inputs():
    history = pd.DataFrame([
        {
            "race_id": f"PREV-{day}",
            "race_date": f"2026-10-{day}",
            "horse_name": f"架空馬{n}",
            "finish_position": n,
            "distance_m": 1600,
            "post_position": n,
            "jockey": f"架空騎手{n}",
            "trainer": f"架空調教師{n}",
        }
        for day in ("15", "17") for n in range(1, 5)
    ])
    entries = pd.DataFrame([
        {
            "race_id": RACE,
            "race_date": "2026-10-25",
            "horse_name": f"架空馬{n}",
            "distance_m": 3000,
            "post_position": n,
            "jockey": f"架空騎手{n}",
            "trainer": f"架空調教師{n}",
        }
        for n in range(1, 5)
    ])
    manifest = ChampionManifest.create(
        feature_columns=["distance_m"],
        categorical_columns=[],
        train_start="2021-01-01",
        train_end="2024-12-31",
        model_version="strict-oddsfree-fictional-only-v1",
        source_id="synthetic-test-fixture",
    )
    manifest = replace(manifest, created_at="2026-10-23T12:00:00+09:00")
    champion = LoadedChampion(model=FakeFittedModel(), manifest=manifest)
    return champion, history, entries


def _run(champion=None, history=None, entries=None, expected=None, asof=AS_OF):
    base_champion, base_history, base_entries = _inputs()
    return private_sunday_ai_preview(
        champion=base_champion if champion is None else champion,
        history=base_history if history is None else history,
        entries=base_entries if entries is None else entries,
        expected_race_ids=(RACE,) if expected is None else expected,
        race_date="2026-10-25",
        observed_at=asof,
    )


def test_synthetic_fitted_model_is_called_and_never_approves_note():
    result = _run()
    assert result["status"] == "PRIVATE_MODEL_RESEARCH_ONLY"
    assert result["modelVersion"].startswith("strict-oddsfree-")
    assert result["races"][0]["modelTopThree"] == ["架空馬1", "架空馬2", "架空馬3"]
    assert result["raceCount"] == 1
    assert result["runnerCount"] == 4
    assert result["publicationAuthorized"] is False
    assert result["notePublishingPermitted"] is False
    assert result["independentOutsiderModelVerified"] is False
    assert result["predictionAccuracyOrEVProven"] is False
    assert len(result["modelOutputSha256"]) == 64
    assert result["publicationAuthorized"] is False


def test_legacy_champion_v7_is_always_rejected():
    c, _, _ = _inputs()
    # ChampionManifest is frozen; create a new manifest instead of mutating.
    c.manifest = ChampionManifest.create(
        feature_columns=["distance_m"], categorical_columns=[],
        train_start="2021-01-01", train_end="2021-07-31",
        model_version="champion-v7", source_id="test",
    )
    with pytest.raises(ValueError, match="legacy Champion"):
        _run(champion=c)


@pytest.mark.parametrize("column", [
    "win_odds", "popularity", "market_rank", "strength",
    "upside_score", "predicted_win_probability", "finish_position",
])
def test_user_or_market_supplied_scores_cannot_enter_future_model(column):
    _, _, entries = _inputs()
    entries[column] = 1.2
    with pytest.raises(ValueError, match="market|future finish"):
        _run(entries=entries)


def test_stale_history_cannot_use_bypass_or_handwritten_score():
    _, history, _ = _inputs()
    history["race_date"] = "2021-07-31"
    with pytest.raises(ValueError, match="stale"):
        _run(history=history)


def test_missing_unconfirmed_or_duplicate_race_entries_are_refused():
    _, _, entries = _inputs()
    with pytest.raises(ValueError, match="incomplete"):
        _run(entries=entries.iloc[:3])
    bad = entries.copy()
    bad.loc[1, "horse_name"] = bad.loc[0, "horse_name"]
    with pytest.raises(ValueError, match="duplicate"):
        _run(entries=bad)
    bad = entries.copy()
    bad.loc[1, "post_position"] = bad.loc[0, "post_position"]
    with pytest.raises(ValueError, match="numbers"):
        _run(entries=bad)
    with pytest.raises(ValueError, match="expected Sunday races"):
        _run(expected=("JRA-20261025-KYOTO-11", "JRA-20261025-TOKYO-01"))


def test_target_race_date_and_observation_boundary():
    _, _, entries = _inputs()
    bad = entries.copy()
    bad["race_date"] = "2026-10-24"
    with pytest.raises(ValueError, match="historical/target race time boundary"):
        _run(entries=bad)
    with pytest.raises(ValueError, match="within two days"):
        _run(asof=datetime.fromisoformat("2026-10-20T12:00:00+09:00"))
    with pytest.raises(ValueError, match="before Sunday"):
        _run(asof=datetime.fromisoformat("2026-10-25T09:00:00+09:00"))


def test_mismatched_race_id_date_and_invalid_model_features():
    with pytest.raises(ValueError, match="target Sunday date"):
        _run(expected=("JRA-20261024-KYOTO-11",))
    champion, _, _ = _inputs()
    champion.manifest = ChampionManifest.create(
        feature_columns=["distance_m", "win_odds"], categorical_columns=[],
        train_start="2021-01-01", train_end="2024-12-31",
        model_version="strict-oddsfree-fictional-only-v1", source_id="test",
    )
    with pytest.raises(ValueError, match="model features"):
        _run(champion=champion)


def test_research_preview_never_ranks_an_unscored_horse():
    _, _, entries = _inputs()
    extra = deepcopy(entries.iloc[[0]])
    extra["horse_name"] = "追加の架空馬"
    extra["post_position"] = 5
    result = _run(entries=pd.concat([entries, extra], ignore_index=True))
    assert result["runnerCount"] == 5
    assert len(result["races"][0]["modelTopThree"]) == 3
    assert result["publicationAuthorized"] is False



def test_historical_market_columns_never_reach_model_feature_builder(monkeypatch):
    import horse_racing_predictions.sunday_ai_research as mod
    original = mod.predict_future_entries
    observed = {"called": False}

    def capture(champion, history, entries, **kwargs):
        observed["called"] = True
        assert "win_odds" not in history
        assert "market_popularity" not in history
        assert "単 勝" not in history
        assert "ｵｯｽﾞ" not in history
        return original(champion, history, entries, **kwargs)

    monkeypatch.setattr(mod, "predict_future_entries", capture)
    _, history, _ = _inputs()
    history["win_odds"] = [2.0] * len(history)
    history["market_popularity"] = [1] * len(history)
    history["単 勝"] = ["100"] * len(history)
    history["ｵｯｽﾞ"] = ["2.5"] * len(history)
    assert _run(history=history)["status"] == "PRIVATE_MODEL_RESEARCH_ONLY"
    assert observed["called"]


def test_historical_odds_perturbations_do_not_change_model_output_digest():
    _, history, _ = _inputs()
    baseline = _run(history=history)
    changed = history.copy()
    changed["win_odds"] = [None, -3, 2.0, 100.0] * 2
    changed["人気 順位"] = [99] * len(changed)
    changed["ｵｯｽﾞ"] = [1.5] * len(changed)
    alternative = _run(history=changed)
    assert baseline["races"] == alternative["races"]
    assert baseline["modelOutputSha256"] == alternative["modelOutputSha256"]
    assert alternative["publicationAuthorized"] is False


def test_model_created_after_prediction_cutoff_is_not_accepted():
    c, _, _ = _inputs()
    c.manifest = replace(c.manifest, created_at="2026-10-25T12:00:00+09:00")
    with pytest.raises(ValueError, match="predate"):
        _run(champion=c)


def test_invalid_or_protected_training_dates_are_blocked():
    champion, _, _ = _inputs()
    for invalid in ("2026-10-01", "2024-2-01", "2020-01-01"):
        case = replace(champion.manifest, train_end=invalid)
        # For 2020-01-01, the model is invalid because train_start=2021-01-01.
        with pytest.raises(ValueError, match="training window|holdout"):
            _run(champion=LoadedChampion(model=FakeFittedModel(), manifest=case))


def test_same_day_history_is_rejected_without_a_verified_event_timestamp():
    _, history, _ = _inputs()
    history.loc[0, "race_date"] = "2026-10-24"
    with pytest.raises(ValueError, match="same-day"):
        _run(history=history)


def test_market_column_unicode_variants_rejected_from_entry_input():
    _, _, entries = _inputs()
    for name in ("ｵｯｽﾞ", "人 気 順 位", "単 勝"):
        altered = entries.copy()
        altered[name] = 1
        with pytest.raises(ValueError, match="market"):
            _run(entries=altered)


def test_model_output_digest_does_not_grant_provenance_or_publication():
    evidence = _run()
    assert evidence["modelOutputSha256"]
    assert evidence["modelTrainingAndProvenanceIndependentlyVerified"] is False
    assert evidence["sourceRightsVerified"] is False
    assert evidence["notePublishingPermitted"] is False
