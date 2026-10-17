import pandas as pd
import pytest

import horse_racing_predictions.exotic_pedigree_phase12 as phase12


EXPECTED_FEATURES = (
    "sire_past_starts",
    "sire_past_win_rate",
    "sire_past_top3_rate",
    "sire_past_avg_finish_percentile",
    "sire_days_since_seen",
    "damsire_past_starts",
    "damsire_past_win_rate",
    "damsire_past_top3_rate",
    "damsire_past_avg_finish_percentile",
    "damsire_days_since_seen",
)


def _history():
    rows = []
    for year in range(2017, 2025):
        for post in range(1, 5):
            rows.append({
                "race_id": f"{year}-01-10:R1",
                "race_date": f"{year}-01-10",
                "horse_name": f"H{post}",
                "finish_position": post,
                "post_position": post,
                "win_odds": {
                    1: 10.0,
                    2: 12.0,
                    3: 3.0,
                    4: 20.0,
                }[post],
                "racecourse": "京都",
                "surface": "芝",
                "distance_m": 1600,
                "jockey": f"J{post}",
                "trainer": f"T{post}",
                "_jv_blood_registration_number": f"B{post}",
            })
    return pd.DataFrame(rows)


def _pedigree():
    return pd.DataFrame([
        {
            "blood_registration_number": f"B{post}",
            "sire_breeding_registration_number": "S1",
            "damsire_breeding_registration_number": "D1",
        }
        for post in range(1, 5)
    ])


class FakeTop3Model:
    constructed_features = []

    def __init__(self, feature_columns, **kwargs):
        self.feature_columns = list(feature_columns)
        type(self).constructed_features.append(
            tuple(self.feature_columns)
        )

    def fit(self, frame, target):
        return self

    def predict_probability(self, frame):
        pedigree = "sire_past_starts" in self.feature_columns
        post = pd.to_numeric(
            frame["post_position"],
            errors="raise",
        )
        if pedigree:
            values = post.le(3).map(
                {True: 0.80, False: 0.20}
            )
        else:
            values = post.le(3).map(
                {True: 0.65, False: 0.35}
            )
        return pd.Series(
            values.to_numpy(dtype=float),
            index=frame.index,
        )


def test_phase12_feature_set_is_exactly_preregistered():
    assert phase12.PHASE12_PEDIGREE_FEATURES == EXPECTED_FEATURES
    assert all(
        "registration_number" not in feature
        for feature in phase12.PHASE12_PEDIGREE_FEATURES
    )


def test_phase12_rejects_post2024_history_before_model_fit(monkeypatch):
    history = _history()
    extra = history.iloc[[0]].copy()
    extra["race_id"] = "2025-01-10:R1"
    extra["race_date"] = "2025-01-10"
    history = pd.concat([history, extra], ignore_index=True)

    def forbidden(*args, **kwargs):
        raise AssertionError("model must not be constructed")

    monkeypatch.setattr(
        phase12,
        "Top3ProbabilityModel",
        forbidden,
    )

    with pytest.raises(RuntimeError, match="post-2024"):
        phase12.evaluate_pedigree_phase12(
            history,
            _pedigree(),
        )


def test_phase12_requires_independent_jv_blood_linkage():
    history = _history().drop(
        columns=["_jv_blood_registration_number"]
    )
    with pytest.raises(ValueError, match="_jv_blood_registration_number"):
        phase12.evaluate_pedigree_phase12(
            history,
            _pedigree(),
        )


def test_phase12_synthetic_e2e_uses_same_baseline_plus_only_ten_pedigree_features(
    monkeypatch,
):
    FakeTop3Model.constructed_features = []
    monkeypatch.setattr(
        phase12,
        "Top3ProbabilityModel",
        FakeTop3Model,
    )

    result = phase12.evaluate_pedigree_phase12(
        _history(),
        _pedigree(),
    )

    assert result["status"] == "research_only_exotic_pedigree_phase12"
    assert result["research_protocol"]["one_real_evaluation_only"] is True
    assert result["research_protocol"]["ranking_metrics_gate"] is False
    assert result["research_protocol"]["final_holdout"] == "2025-2026 untouched"
    assert result["feature_design"]["raw_pedigree_ids_as_features"] is False
    assert result["feature_design"]["pedigree_features"] == list(
        EXPECTED_FEATURES
    )

    assert len(FakeTop3Model.constructed_features) == 2
    baseline, challenger = FakeTop3Model.constructed_features
    assert tuple(challenger[:len(baseline)]) == baseline
    assert tuple(challenger[len(baseline):]) == EXPECTED_FEATURES
    assert all(
        "registration_number" not in column
        for column in challenger
    )

    for year in ("evaluation_2023", "evaluation_2024"):
        evaluation = result[year]
        assert evaluation["binary_log_loss_delta"] < 0
        assert evaluation["brier_delta"] < 0
        bootstrap = evaluation["paired_bootstrap_vs_baseline"]
        assert (
            bootstrap["binary_log_loss_improvement_support"]
            >= 0.80
        )
        assert bootstrap["brier_improvement_support"] >= 0.80

    assert result["development_pedigree_gate_passed"] is True
