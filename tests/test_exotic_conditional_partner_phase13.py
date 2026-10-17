import pandas as pd
import pytest

import horse_racing_predictions.exotic_conditional_partner_phase13 as phase13


def _row(
    *,
    race_id,
    runner,
    finish,
    odds,
    market_probability,
    market_rank,
    strength,
):
    return {
        "race_id": race_id,
        "runner": runner,
        "finish_position": finish,
        "win_odds": odds,
        "market_implied_probability": market_probability,
        "market_probability_rank": market_rank,
        "candidate_strength": strength,
        "horse_recent_top3_rate_5": strength,
        "horse_recent_finish_percentile_mean_5": 1.0 - strength,
        "horse_recent_early_ratio_mean_5": strength * 0.5,
        "horse_recent_late_ratio_mean_5": strength * 0.6,
        "jockey_past_win_rate": strength * 0.2,
        "jockey_course_past_win_rate": strength * 0.15,
        "horse_jockey_past_win_rate": strength * 0.1,
        "trainer_past_win_rate": strength * 0.12,
    }


def _frame():
    return pd.DataFrame([
        _row(
            race_id="R1",
            runner="favorite",
            finish=4,
            odds=2.0,
            market_probability=0.40,
            market_rank=1,
            strength=0.80,
        ),
        _row(
            race_id="R1",
            runner="anchor",
            finish=3,
            odds=10.0,
            market_probability=0.10,
            market_rank=4,
            strength=0.65,
        ),
        _row(
            race_id="R1",
            runner="partner_a",
            finish=1,
            odds=4.0,
            market_probability=0.25,
            market_rank=2,
            strength=0.70,
        ),
        _row(
            race_id="R1",
            runner="partner_b",
            finish=2,
            odds=5.0,
            market_probability=0.20,
            market_rank=3,
            strength=0.60,
        ),
        _row(
            race_id="R1",
            runner="wrong",
            finish=5,
            odds=15.0,
            market_probability=0.05,
            market_rank=5,
            strength=0.40,
        ),
    ])


def _probability(frame):
    values = {
        "favorite": 0.95,
        "anchor": 0.70,
        "partner_a": 0.65,
        "partner_b": 0.55,
        "wrong": 0.60,
    }
    return pd.Series(
        [values[name] for name in frame["runner"]],
        index=frame.index,
        dtype=float,
    )


def test_anchor_nomination_uses_longshot_probability_not_finish_or_favorite():
    frame = _frame()
    probability = _probability(frame)

    pairs, features, metadata = phase13.build_conditional_partner_frame(
        frame,
        probability,
        base_feature_columns=("candidate_strength",),
    )

    # Favorite has highest probability but odds < 6, so it cannot be the anchor.
    # The anchor is the highest-probability member of the frozen longshot proxy.
    assert metadata["races_with_longshot_anchor_candidate"] == 1
    assert metadata["nominated_anchor_top3_count"] == 1
    assert metadata["nominated_anchor_top3_hit_rate"] == 1.0
    assert metadata["conditional_partner_races"] == 1
    assert len(pairs) == 4

    anchor_probability = pairs["anchor_general_probability"].unique()
    assert anchor_probability.tolist() == [0.70]
    assert "finish_position" not in features
    assert "win_odds" not in features
    assert all("registration_number" not in name for name in features)


def test_partner_evidence_can_improve_exact_pair_and_recall():
    frame = _frame()
    probability = _probability(frame)
    pairs, _, _ = phase13.build_conditional_partner_frame(
        frame,
        probability,
        base_feature_columns=("candidate_strength",),
    )

    # Baseline general probabilities choose partner_a + wrong.
    # Challenger deliberately scores the two true partners highest.
    challenger = pd.Series(
        [
            {
                "favorite": 0.10,
                "partner_a": 0.90,
                "partner_b": 0.80,
                "wrong": 0.70,
            }[runner]
            for runner in pairs["runner"]
        ],
        index=pairs.index,
        dtype=float,
    )

    evidence = phase13.partner_selection_evidence(
        pairs,
        challenger,
    )

    assert len(evidence) == 1
    row = evidence.iloc[0]
    assert row["baseline_exact_pair_hit"] == 0
    assert row["challenger_exact_pair_hit"] == 1
    assert row["baseline_recall_at_2"] == 0.5
    assert row["challenger_recall_at_2"] == 1.0


def test_partner_bootstrap_reports_full_support_when_every_race_improves():
    evidence = pd.DataFrame([
        {
            "race_id": f"R{idx}",
            "baseline_exact_pair_hit": 0,
            "challenger_exact_pair_hit": 1,
            "baseline_recall_at_2": 0.5,
            "challenger_recall_at_2": 1.0,
        }
        for idx in range(1, 6)
    ])

    result = phase13.paired_race_bootstrap_partner_selection(
        evidence,
        samples=100,
        seed=20261006,
    )

    assert result["exact_pair_hit_improvement_support"] == 1.0
    assert result["recall_at_2_improvement_support"] == 1.0
    assert result["exact_pair_hit_delta_ci90"] == [1.0, 1.0]
    assert result["recall_at_2_delta_ci90"] == [0.5, 0.5]


def test_conditional_sample_excludes_anchor_miss_but_reports_it():
    frame = _frame()
    frame.loc[
        frame["runner"].eq("anchor"),
        "finish_position",
    ] = 5
    frame.loc[
        frame["runner"].eq("wrong"),
        "finish_position",
    ] = 3

    pairs, _, metadata = phase13.build_conditional_partner_frame(
        frame,
        _probability(frame),
        base_feature_columns=("candidate_strength",),
    )

    assert metadata["races_with_longshot_anchor_candidate"] == 1
    assert metadata["nominated_anchor_top3_count"] == 0
    assert metadata["nominated_anchor_top3_hit_rate"] == 0.0
    assert metadata["conditional_partner_races"] == 0
    assert pairs.empty


def test_phase13_rejects_post2024_rows_before_feature_construction(monkeypatch):
    history = pd.DataFrame([
        {
            "race_id": "2025:R1",
            "race_date": "2025-01-01",
            "finish_position": 1,
            "win_odds": 10.0,
        }
    ])

    def forbidden(*args, **kwargs):
        raise AssertionError("feature construction must not run")

    monkeypatch.setattr(
        phase13,
        "build_pre_race_features",
        forbidden,
    )

    with pytest.raises(RuntimeError, match="post-2024"):
        phase13.evaluate_conditional_partner_phase13(history)


def test_phase13_preregistered_constants_are_frozen():
    assert phase13.PHASE13_OOF_YEARS == (
        2018,
        2019,
        2020,
        2021,
        2022,
    )
    assert phase13.PHASE13_ITERATIONS == 300
    assert phase13.PHASE13_DEPTH == 7
    assert phase13.PHASE13_LEARNING_RATE == 0.05
    assert phase13.PHASE13_RANDOM_SEED == 42
    assert len(phase13.PHASE13_PAIR_CONTEXT_FEATURES) == 15
