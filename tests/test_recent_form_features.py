import pandas as pd

from horse_racing_predictions.data_sources import normalize_jra_history
from horse_racing_predictions.features import build_pre_race_features

def test_optional_postrace_columns_are_normalized():
    raw = pd.DataFrame({
        "レースID": ["R1"],
        "レース日付": ["2026-01-01"],
        "着順": [1],
        "馬名": ["H1"],
        "単勝": [3.0],
        "上り": [34.2],
        "1コーナー": [2],
        "2コーナー": [3],
        "3コーナー": [2],
        "4コーナー": [1],
        "競争条件": ["3勝クラス"],
        "リステッド・重賞競走": ["G3"],
    })
    out = normalize_jra_history(raw)
    assert out.loc[0, "last_3f"] == 34.2
    assert out.loc[0, "corner_1"] == 2
    assert out.loc[0, "race_class"] == "3勝クラス"
    assert out.loc[0, "graded_race"] == "G3"

def test_recent_form_uses_prior_days_only():
    rows = []
    for day, finish, last3f, corner in [
        (1, 1, 34.0, 1),
        (2, 5, 35.0, 5),
        (3, 2, 33.8, 2),
        (4, 4, 35.2, 6),
    ]:
        rows.append({
            "race_id": f"R{day}",
            "race_date": f"2026-01-0{day}",
            "horse_name": "H1",
            "finish_position": finish,
            "win_odds": 4.0,
            "distance_m": 1600,
            "post_position": 2,
            "carried_weight": 55,
            "horse_weight": 480,
            "last_3f": last3f,
            "corner_1": corner,
            "corner_2": corner,
            "corner_3": corner,
            "corner_4": corner,
            "race_class": "OPEN",
            "graded_race": "NONE",
        })

    result = build_pre_race_features(pd.DataFrame(rows))
    df = result.frame

    first = df.iloc[0]
    assert pd.isna(first["horse_recent_finish_mean_3"])
    assert pd.isna(first["horse_recent_last_3f_mean_3"])

    fourth = df.iloc[3]
    assert abs(fourth["horse_recent_finish_mean_3"] - (1+5+2)/3) < 1e-12
    assert abs(fourth["horse_recent_last_3f_mean_3"] - (34.0+35.0+33.8)/3) < 1e-12
    assert abs(fourth["horse_recent_win_rate_3"] - 1/3) < 1e-12

def test_current_race_postrace_values_are_not_model_features():
    frame = pd.DataFrame([{
        "race_id": "R1",
        "race_date": "2026-01-01",
        "horse_name": "H1",
        "finish_position": 1,
        "win_odds": 3.0,
        "last_3f": 33.5,
        "corner_1": 1,
        "corner_2": 1,
        "corner_3": 1,
        "corner_4": 1,
    }])
    result = build_pre_race_features(frame)
    features = set(result.feature_columns)
    for forbidden in (
        "last_3f", "corner_1", "corner_2", "corner_3", "corner_4"
    ):
        assert forbidden not in features
    assert "horse_recent_last_3f_mean_3" in features

def test_relative_race_features_are_available_pre_race():
    frame = pd.DataFrame([
        {
            "race_id": "R1", "race_date": "2026-01-01",
            "horse_name": "A", "finish_position": 1, "win_odds": 2.0,
            "post_position": 1, "carried_weight": 54, "horse_weight": 460,
        },
        {
            "race_id": "R1", "race_date": "2026-01-01",
            "horse_name": "B", "finish_position": 2, "win_odds": 3.0,
            "post_position": 2, "carried_weight": 56, "horse_weight": 500,
        },
    ])
    result = build_pre_race_features(frame)
    row = result.frame.iloc[0]
    assert row["field_size"] == 2
    assert row["relative_post_position"] == 0.5
    assert row["carried_weight_vs_race_mean"] == -1.0
    assert row["horse_weight_vs_race_mean"] == -20.0
