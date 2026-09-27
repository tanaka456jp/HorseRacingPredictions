import pandas as pd

from horse_racing_predictions.features import (
    build_pre_race_features,
)


def _row(
    race_id,
    race_date,
    horse_name,
    jockey,
    trainer,
    finish,
    post,
):
    return {
        "race_id": race_id,
        "race_date": race_date,
        "horse_name": horse_name,
        "jockey": jockey,
        "trainer": trainer,
        "finish_position": finish,
        "win_odds": 3.0 + post,
        "distance_m": 1600,
        "post_position": post,
        "age": 3,
        "carried_weight": 55,
        "horse_weight": 470 + post,
        "horse_weight_delta": 0,
        "racecourse": "Kyoto",
        "surface": "Turf",
        "weather": "Fine",
        "track_condition": "Good",
        "sex": "M",
        "race_class": "OPEN",
        "graded_race": "NONE",
    }


def test_ranker_v10_features_are_opt_in_only():
    frame = pd.DataFrame([
        _row(
            "R1", "2026-01-01", "H1", "J1", "T1", 1, 1
        ),
        _row(
            "R1", "2026-01-01", "H2", "J2", "T2", 2, 2
        ),
    ])

    standard = build_pre_race_features(frame)
    enhanced = build_pre_race_features(
        frame,
        experimental_ranker_v10=True,
    )

    assert (
        "horse_past_avg_finish_percentile"
        not in standard.feature_columns
    )
    assert (
        "horse_jockey_past_starts"
        not in standard.feature_columns
    )
    assert (
        "horse_past_avg_finish_percentile"
        in enhanced.feature_columns
    )
    assert (
        "horse_jockey_past_starts"
        in enhanced.feature_columns
    )


def test_ranker_v10_finish_percentile_uses_prior_day_only():
    rows = [
        _row(
            "R1", "2026-01-01", "H1", "J1", "T1", 2, 1
        ),
        _row(
            "R1", "2026-01-01", "A", "JA", "TA", 1, 2
        ),
        _row(
            "R1", "2026-01-01", "B", "JB", "TB", 3, 3
        ),
        _row(
            "R1", "2026-01-01", "C", "JC", "TC", 4, 4
        ),
        _row(
            "R2", "2026-01-02", "H1", "J1", "T1", 1, 1
        ),
        _row(
            "R2", "2026-01-02", "D", "JD", "TD", 2, 2
        ),
        _row(
            "R2", "2026-01-02", "E", "JE", "TE", 3, 3
        ),
    ]
    frame = pd.DataFrame(rows)

    built = build_pre_race_features(
        frame,
        experimental_ranker_v10=True,
    ).frame

    first = built.loc[
        (built["race_id"] == "R1")
        & (built["horse_name"] == "H1")
    ].iloc[0]
    second = built.loc[
        (built["race_id"] == "R2")
        & (built["horse_name"] == "H1")
    ].iloc[0]

    assert pd.isna(
        first["horse_past_avg_finish_percentile"]
    )
    assert abs(
        second["horse_past_avg_finish_percentile"]
        - (1.0 / 3.0)
    ) < 1e-12
    assert abs(
        second[
            "horse_recent_finish_percentile_mean_3"
        ]
        - (1.0 / 3.0)
    ) < 1e-12


def test_ranker_v10_interaction_history_does_not_use_same_day():
    frame = pd.DataFrame([
        _row(
            "D1R1", "2026-01-01", "H1", "J1", "T1", 1, 1
        ),
        _row(
            "D1R1", "2026-01-01", "A", "JA", "TA", 2, 2
        ),
        _row(
            "D1R2", "2026-01-01", "H2", "J1", "T1", 2, 1
        ),
        _row(
            "D1R2", "2026-01-01", "B", "JB", "TB", 1, 2
        ),
        _row(
            "D2R1", "2026-01-02", "H1", "J1", "T1", 1, 1
        ),
        _row(
            "D2R1", "2026-01-02", "C", "JC", "TC", 2, 2
        ),
    ])

    built = build_pre_race_features(
        frame,
        experimental_ranker_v10=True,
    ).frame

    day1 = built.loc[
        built["race_date"].eq(
            pd.Timestamp("2026-01-01")
        )
        & built["jockey"].eq("J1")
    ]
    day2 = built.loc[
        built["race_date"].eq(
            pd.Timestamp("2026-01-02")
        )
        & built["jockey"].eq("J1")
    ].iloc[0]

    assert (
        day1["jockey_trainer_past_starts"] == 0
    ).all()
    assert day2["jockey_trainer_past_starts"] == 2
    assert day2["horse_jockey_past_starts"] == 1
