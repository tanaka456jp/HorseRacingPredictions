import pandas as pd
import pytest

import horse_racing_predictions.exotic_conditional_partner_phase13 as phase13


def _oof_frame():
    rows = []
    # Two races per year so each validation year has conditional partner data.
    for year in range(2017, 2023):
        for race_no in (1, 2):
            race_id = f"{year}:R{race_no}"
            runners = [
                # anchor candidate and two true partners
                ("anchor", 3, 10.0, 0.10, 4, 0.60),
                ("p1", 1, 3.0, 0.35, 1, 0.80),
                ("p2", 2, 4.0, 0.25, 2, 0.70),
                ("other", 4, 8.0, 0.15, 3, 0.40),
            ]
            for post, (name, finish, odds, market_p, market_rank, strength) in enumerate(
                runners,
                start=1,
            ):
                row = {
                    "race_id": race_id,
                    "race_date": pd.Timestamp(f"{year}-06-{race_no:02d}"),
                    "horse_name": f"{name}-{year}-{race_no}",
                    "finish_position": finish,
                    "win_odds": odds,
                    "post_position": post,
                    "racecourse": "京都",
                    "surface": "芝",
                    "distance_m": 1600,
                    "market_implied_probability": market_p,
                    "market_probability_rank": market_rank,
                    "horse_recent_top3_rate_5": strength,
                    "horse_recent_finish_percentile_mean_5": 1.0 - strength,
                    "horse_recent_early_ratio_mean_5": strength * 0.5,
                    "horse_recent_late_ratio_mean_5": strength * 0.6,
                    "jockey_past_win_rate": strength * 0.2,
                    "jockey_course_past_win_rate": strength * 0.15,
                    "horse_jockey_past_win_rate": strength * 0.1,
                    "trainer_past_win_rate": strength * 0.12,
                    "base": strength,
                }
                rows.append(row)
    return pd.DataFrame(rows)


class RecordingTop3Model:
    fits = []
    predictions = []

    def __init__(self, feature_columns, **kwargs):
        self.feature_columns = list(feature_columns)

    def fit(self, frame, target):
        dates = pd.to_datetime(frame["race_date"], errors="raise")
        type(self).fits.append({
            "min": dates.min(),
            "max": dates.max(),
            "rows": len(frame),
        })
        return self

    def predict_probability(self, frame):
        dates = pd.to_datetime(frame["race_date"], errors="raise")
        type(self).predictions.append({
            "min": dates.min(),
            "max": dates.max(),
            "rows": len(frame),
        })
        # Ensure the odds>=6 longshot anchor wins nomination.
        values = frame["win_odds"].map(
            lambda value: 0.8 if float(value) == 10.0 else (
                0.7 if float(value) == 8.0 else 0.5
            )
        )
        return pd.Series(values.to_numpy(dtype=float), index=frame.index)


def test_oof_anchor_predictions_are_strictly_future_of_each_training_fold(monkeypatch):
    RecordingTop3Model.fits = []
    RecordingTop3Model.predictions = []
    monkeypatch.setattr(
        phase13,
        "Top3ProbabilityModel",
        RecordingTop3Model,
    )

    frame = _oof_frame()
    training, pair_features, folds = phase13._build_oof_partner_training(
        frame,
        ("base",),
    )

    assert len(folds) == len(phase13.PHASE13_OOF_YEARS)
    assert not training.empty
    assert pair_features[0] == "base"

    assert len(RecordingTop3Model.fits) == 5
    assert len(RecordingTop3Model.predictions) == 5

    for expected_year, fit, prediction in zip(
        phase13.PHASE13_OOF_YEARS,
        RecordingTop3Model.fits,
        RecordingTop3Model.predictions,
    ):
        assert fit["max"] < pd.Timestamp(f"{expected_year}-01-01")
        assert prediction["min"].year == expected_year
        assert prediction["max"].year == expected_year
        assert fit["max"] < prediction["min"]


def test_oof_folds_are_fixed_and_never_include_2023_or_2024():
    assert phase13.PHASE13_OOF_YEARS == (2018, 2019, 2020, 2021, 2022)
    assert 2023 not in phase13.PHASE13_OOF_YEARS
    assert 2024 not in phase13.PHASE13_OOF_YEARS


def test_pair_feature_list_contains_only_frozen_context_after_base_features():
    frame = _oof_frame()
    probability = pd.Series(
        [
            0.8 if float(value) == 10.0 else (
                0.7 if float(value) == 8.0 else 0.5
            )
            for value in frame["win_odds"]
        ],
        index=frame.index,
        dtype=float,
    )
    pairs, features, metadata = phase13.build_conditional_partner_frame(
        frame.loc[frame["race_date"].dt.year.eq(2022)].copy(),
        probability.loc[frame["race_date"].dt.year.eq(2022)],
        base_feature_columns=("base",),
    )
    assert not pairs.empty
    assert features == (
        "base",
        *phase13.PHASE13_PAIR_CONTEXT_FEATURES,
    )
    assert metadata["conditional_partner_races"] == 2


def test_pair_feature_builder_rejects_forbidden_outcome_or_raw_id_base_features():
    frame = _oof_frame()
    validation = frame.loc[frame["race_date"].dt.year.eq(2022)].copy()
    probability = pd.Series(
        0.5,
        index=validation.index,
        dtype=float,
    )

    for forbidden in (
        "finish_position",
        "win_odds",
        "_jv_blood_registration_number",
        "sire_breeding_registration_number",
    ):
        with pytest.raises(ValueError, match="forbidden"):
            phase13.build_conditional_partner_frame(
                validation,
                probability,
                base_feature_columns=(forbidden,),
            )
