import pandas as pd

from horse_racing_predictions.features import build_pre_race_features

def test_context_history_uses_only_prior_days():
    raw = pd.DataFrame([
        {
            "race_id": "D1R1", "race_date": "2026-01-01",
            "horse_name": "H1", "jockey": "J1", "trainer": "T1",
            "finish_position": 1, "distance_m": 1600,
            "racecourse": "Kyoto", "surface": "Turf",
            "weather": "Fine", "track_condition": "Good", "sex": "M",
        },
        {
            "race_id": "D1R2", "race_date": "2026-01-01",
            "horse_name": "H1", "jockey": "J1", "trainer": "T1",
            "finish_position": 5, "distance_m": 1600,
            "racecourse": "Kyoto", "surface": "Turf",
            "weather": "Fine", "track_condition": "Good", "sex": "M",
        },
        {
            "race_id": "D2R1", "race_date": "2026-01-02",
            "horse_name": "H1", "jockey": "J1", "trainer": "T1",
            "finish_position": 2, "distance_m": 1600,
            "racecourse": "Kyoto", "surface": "Turf",
            "weather": "Cloudy", "track_condition": "Good", "sex": "M",
        },
    ])

    result = build_pre_race_features(raw)
    frame = result.frame

    day1 = frame[frame["race_date"] == pd.Timestamp("2026-01-01")]
    day2 = frame[frame["race_date"] == pd.Timestamp("2026-01-02")]

    assert (day1["horse_surface_past_starts"] == 0).all()
    assert (day1["horse_course_past_starts"] == 0).all()
    assert (day1["horse_distance_past_starts"] == 0).all()

    row = day2.iloc[0]
    assert row["horse_surface_past_starts"] == 2
    assert row["horse_surface_past_win_rate"] == 0.5
    assert row["horse_course_past_starts"] == 2
    assert row["horse_distance_past_starts"] == 2
    assert row["jockey_course_past_starts"] == 2

def test_context_history_features_are_exposed_to_model():
    raw = pd.DataFrame([
        {
            "race_id": "R1", "race_date": "2026-01-01",
            "horse_name": "H1", "jockey": "J1", "trainer": "T1",
            "finish_position": 1, "distance_m": 1600,
            "racecourse": "Kyoto", "surface": "Turf",
        },
        {
            "race_id": "R2", "race_date": "2026-01-02",
            "horse_name": "H1", "jockey": "J1", "trainer": "T1",
            "finish_position": 2, "distance_m": 1800,
            "racecourse": "Kyoto", "surface": "Turf",
        },
    ])
    result = build_pre_race_features(raw)
    expected = {
        "horse_surface_past_win_rate",
        "horse_course_past_win_rate",
        "horse_distance_past_win_rate",
        "jockey_course_past_win_rate",
        "trainer_course_past_win_rate",
    }
    assert expected.issubset(set(result.feature_columns))
