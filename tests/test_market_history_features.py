import math
import pandas as pd

from horse_racing_predictions.data_sources import normalize_jra_history
from horse_racing_predictions.features import build_pre_race_features


def test_popularity_is_normalized_when_available():
    raw = pd.DataFrame({
        "レースID": ["R1"],
        "レース日付": ["2026-01-01"],
        "着順": [1],
        "馬名": ["H1"],
        "単勝": [4.5],
        "人気": [2],
    })
    out = normalize_jra_history(raw)
    assert out.loc[0, "popularity"] == 2


def test_current_odds_are_not_model_features_but_prior_odds_are():
    rows = [
        {
            "race_id": "R1",
            "race_date": "2026-01-01",
            "horse_name": "H1",
            "finish_position": 4,
            "win_odds": 10.0,
            "popularity": 6,
            "distance_m": 1600,
            "surface": "Turf",
            "racecourse": "Kyoto",
        },
        {
            "race_id": "R2",
            "race_date": "2026-01-02",
            "horse_name": "H1",
            "finish_position": 2,
            "win_odds": 5.0,
            "popularity": 3,
            "distance_m": 1800,
            "surface": "Turf",
            "racecourse": "Kyoto",
        },
        {
            "race_id": "R3",
            "race_date": "2026-01-03",
            "horse_name": "H1",
            "finish_position": 3,
            "win_odds": 4.0,
            "popularity": 2,
            "distance_m": 1800,
            "surface": "Dirt",
            "racecourse": "Tokyo",
        },
        {
            "race_id": "R4",
            "race_date": "2026-01-04",
            "horse_name": "H1",
            "finish_position": 1,
            "win_odds": 2.0,
            "popularity": 1,
            "distance_m": 2000,
            "surface": "Turf",
            "racecourse": "Nakayama",
        },
    ]

    result = build_pre_race_features(pd.DataFrame(rows))
    features = set(result.feature_columns)
    frame = result.frame

    assert "win_odds" not in features
    assert "popularity" not in features
    assert "horse_last_odds" in features
    assert "horse_recent_log_odds_mean_3" in features
    assert "horse_recent_popularity_mean_3" in features
    assert "horse_last_distance_m" in features
    assert "horse_last_surface" in features
    assert "horse_last_racecourse" in features

    assert pd.isna(frame.iloc[0]["horse_last_odds"])
    fourth = frame.iloc[3]
    assert fourth["horse_last_odds"] == 4.0
    assert fourth["horse_last_popularity"] == 2
    assert fourth["horse_last_distance_m"] == 1800
    assert fourth["horse_last_surface"] == "Dirt"
    assert fourth["horse_last_racecourse"] == "Tokyo"

    expected_log_odds = (
        math.log(10.0) + math.log(5.0) + math.log(4.0)
    ) / 3.0
    assert abs(
        fourth["horse_recent_log_odds_mean_3"] - expected_log_odds
    ) < 1e-12
    assert abs(
        fourth["horse_recent_popularity_mean_3"] - (6 + 3 + 2) / 3
    ) < 1e-12


def test_same_day_market_information_is_excluded():
    rows = [
        {
            "race_id": "D1R1",
            "race_date": "2026-01-01",
            "horse_name": "H1",
            "finish_position": 2,
            "win_odds": 6.0,
            "popularity": 4,
        },
        {
            "race_id": "D1R2",
            "race_date": "2026-01-01",
            "horse_name": "H1",
            "finish_position": 3,
            "win_odds": 10.0,
            "popularity": 7,
        },
        {
            "race_id": "D2R1",
            "race_date": "2026-01-02",
            "horse_name": "H1",
            "finish_position": 1,
            "win_odds": 2.5,
            "popularity": 1,
        },
    ]

    frame = build_pre_race_features(pd.DataFrame(rows)).frame
    day1 = frame[frame["race_date"] == pd.Timestamp("2026-01-01")]
    day2 = frame[frame["race_date"] == pd.Timestamp("2026-01-02")]

    assert day1["horse_last_odds"].isna().all()
    assert day1["horse_recent_log_odds_mean_3"].isna().all()

    # Same-day source rows are aggregated, then shifted as one historical day.
    assert day2.iloc[0]["horse_last_odds"] == 8.0
    assert abs(
        day2.iloc[0]["horse_recent_log_odds_mean_3"]
        - math.log(8.0)
    ) < 1e-12
