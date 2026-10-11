import pandas as pd

import horse_racing_predictions.exotic_conditional_partner_phase13 as phase13


class FakeGeneralModel:
    fit_periods = []

    def __init__(self, feature_columns, **kwargs):
        self.feature_columns = list(feature_columns)

    def fit(self, frame, target):
        dates = pd.to_datetime(frame["race_date"], errors="raise")
        type(self).fit_periods.append(
            (dates.min(), dates.max(), len(frame))
        )
        return self

    def predict_probability(self, frame):
        # Anchor gets highest probability among odds>=6 longshot candidates.
        values = frame["horse_name"].map(
            lambda name: (
                0.82 if str(name).startswith("anchor")
                else 0.74 if str(name).startswith("partner_a")
                else 0.68 if str(name).startswith("partner_b")
                else 0.60 if str(name).startswith("wrong")
                else 0.50
            )
        )
        return pd.Series(values.to_numpy(dtype=float), index=frame.index)


class FakePartnerRanker:
    fit_rows = 0
    feature_columns_seen = None

    def __init__(self, feature_columns, **kwargs):
        self.feature_columns = list(feature_columns)
        type(self).feature_columns_seen = tuple(feature_columns)

    def fit(self, frame, target_col="is_partner_top3", race_col="_pair_group_id"):
        type(self).fit_rows = len(frame)
        assert frame[target_col].isin([0, 1]).all()
        assert frame.groupby(race_col)[target_col].sum().eq(2).all()
        return self

    def predict_win_probability(self, frame, race_col="_pair_group_id"):
        values = frame["horse_name"].map(
            lambda name: (
                0.95 if str(name).startswith("partner_a")
                else 0.90 if str(name).startswith("partner_b")
                else 0.20
            )
        ).astype(float)
        # Only ranking matters for this research model; preserve row index.
        return pd.Series(values.to_numpy(), index=frame.index, dtype=float)


def _history():
    rows = []
    for year in range(2017, 2025):
        for month in (1, 4, 7, 10):
            race_id = f"{year}-{month:02d}:R1"
            runners = [
                # General baseline will prefer wrong over partner_b,
                # while Phase 13 partner ranker will recover the true pair.
                ("favorite", 4, 2.0, "J1", "T1"),
                ("anchor", 3, 10.0, "J2", "T2"),
                ("partner_a", 1, 4.0, "J3", "T3"),
                ("partner_b", 2, 5.0, "J4", "T4"),
                ("wrong", 5, 8.0, "J5", "T5"),
            ]
            for post, (name, finish, odds, jockey, trainer) in enumerate(
                runners,
                start=1,
            ):
                rows.append({
                    "race_id": race_id,
                    "race_date": f"{year}-{month:02d}-10",
                    "horse_name": f"{name}-{year}-{month}",
                    "finish_position": finish,
                    "win_odds": odds,
                    "post_position": post,
                    "racecourse": "京都",
                    "surface": "芝",
                    "distance_m": 1600,
                    "weather": "晴",
                    "track_condition": "良",
                    "sex": "牡",
                    "race_class": "3勝",
                    "graded_race": "0",
                    "jockey": jockey,
                    "trainer": trainer,
                })
    return pd.DataFrame(rows)


def test_phase13_full_synthetic_e2e_respects_chronology_and_improves_partner_selection(
    monkeypatch,
):
    FakeGeneralModel.fit_periods = []
    FakePartnerRanker.fit_rows = 0
    FakePartnerRanker.feature_columns_seen = None

    monkeypatch.setattr(
        phase13,
        "Top3ProbabilityModel",
        FakeGeneralModel,
    )
    monkeypatch.setattr(
        phase13,
        "CatBoostRankingProbabilityModel",
        FakePartnerRanker,
    )

    result = phase13.evaluate_conditional_partner_phase13(
        _history()
    )

    assert result["status"] == "research_only_conditional_partner_phase13"
    assert result["research_protocol"]["one_real_evaluation_only"] is True
    assert result["research_protocol"]["final_holdout"] == "2025-2026 untouched"
    assert result["research_protocol"]["real_ticket_generation"] == "disabled"
    assert result["feature_design"]["raw_identifiers_as_features"] is False
    assert result["feature_design"]["post_race_values_as_features"] is False

    assert FakePartnerRanker.fit_rows > 0
    assert FakePartnerRanker.feature_columns_seen is not None
    assert all(
        "registration_number" not in name
        for name in FakePartnerRanker.feature_columns_seen
    )
    assert "finish_position" not in FakePartnerRanker.feature_columns_seen
    assert "win_odds" not in FakePartnerRanker.feature_columns_seen

    # Five annual OOF general fits plus one frozen through-2022 final fit.
    assert len(FakeGeneralModel.fit_periods) == 6
    oof_fits = FakeGeneralModel.fit_periods[:5]
    for expected_year, (minimum, maximum, _) in zip(
        phase13.PHASE13_OOF_YEARS,
        oof_fits,
    ):
        assert maximum < pd.Timestamp(f"{expected_year}-01-01")

    final_fit = FakeGeneralModel.fit_periods[-1]
    assert final_fit[1] <= pd.Timestamp("2022-12-31")

    for key in ("evaluation_2023", "evaluation_2024"):
        evaluation = result[key]
        assert evaluation["races_with_longshot_anchor_candidate"] > 0
        assert evaluation["nominated_anchor_top3_hit_rate"] == 1.0
        assert evaluation["conditional_partner_races"] > 0
        assert evaluation["exact_partner_pair_hit_rate_delta"] > 0
        assert evaluation["partner_recall_at_2_delta"] > 0
        bootstrap = evaluation["paired_bootstrap_vs_baseline"]
        assert bootstrap["exact_pair_hit_improvement_support"] >= 0.80
        assert bootstrap["recall_at_2_improvement_support"] >= 0.80

    assert result["development_conditional_partner_gate_passed"] is True
