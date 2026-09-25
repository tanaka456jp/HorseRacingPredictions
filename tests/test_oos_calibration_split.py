import pandas as pd

from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.oos import generate_walk_forward_predictions

def test_forward_calibration_is_before_test_period():
    rows = []
    for day in range(1, 41):
        for horse in range(3):
            rows.append({
                "race_id": f"R{day:02d}",
                "race_date": pd.Timestamp("2026-01-01")
                + pd.Timedelta(days=day - 1),
                "horse_name": f"H{horse}",
                "jockey": f"J{horse}",
                "trainer": f"T{horse}",
                "finish_position": 1 if horse == day % 3 else horse + 2,
                "distance_m": 1600,
                "post_position": horse + 1,
                "age": 3,
                "carried_weight": 55,
                "horse_weight": 470 + horse * 10,
                "horse_weight_delta": 0,
                "racecourse": "Kyoto",
                "surface": "Turf",
                "weather": "Fine",
                "track_condition": "Good",
                "sex": "M",
                "win_odds": 3.0 + horse,
            })

    features = build_pre_race_features(pd.DataFrame(rows))
    result = generate_walk_forward_predictions(
        features.frame,
        features.feature_columns,
        min_train_dates=20,
        test_dates=5,
        calibration_dates=5,
    )

    assert result.fold_count > 0
    pred = result.predictions.dropna(subset=["calibration_start"])
    assert not pred.empty
    assert (
        pd.to_datetime(pred["train_end"])
        < pd.to_datetime(pred["calibration_start"])
    ).all()
    assert (
        pd.to_datetime(pred["calibration_start"])
        < pd.to_datetime(pred["test_start"])
    ).all()
