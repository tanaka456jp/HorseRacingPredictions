import pandas as pd

from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.oos import generate_walk_forward_predictions

def test_same_day_results_are_not_used_in_jockey_history():
    raw = pd.DataFrame([
        {
            "race_id": "D1R1", "race_date": "2026-01-01",
            "horse_name": "H1", "jockey": "J1",
            "finish_position": 1, "distance_m": 1600,
            "post_position": 1, "age": 3, "carried_weight": 55,
            "horse_weight": 470, "horse_weight_delta": 0, "win_odds": 3.0,
        },
        {
            "race_id": "D1R2", "race_date": "2026-01-01",
            "horse_name": "H2", "jockey": "J1",
            "finish_position": 2, "distance_m": 1800,
            "post_position": 2, "age": 4, "carried_weight": 56,
            "horse_weight": 480, "horse_weight_delta": 2, "win_odds": 4.0,
        },
        {
            "race_id": "D2R1", "race_date": "2026-01-02",
            "horse_name": "H3", "jockey": "J1",
            "finish_position": 3, "distance_m": 1600,
            "post_position": 3, "age": 3, "carried_weight": 55,
            "horse_weight": 460, "horse_weight_delta": -2, "win_odds": 5.0,
        },
    ])

    built = build_pre_race_features(raw).frame
    first_day = built[built["race_date"] == pd.Timestamp("2026-01-01")]
    second_day = built[built["race_date"] == pd.Timestamp("2026-01-02")]

    assert (first_day["jockey_past_starts"] == 0).all()
    assert second_day.iloc[0]["jockey_past_starts"] == 2
    assert second_day.iloc[0]["jockey_past_win_rate"] == 0.5

def test_walk_forward_oos_probabilities_are_race_normalized():
    rows = []
    horses = ["H1", "H2", "H3"]
    jockeys = ["J1", "J2", "J3"]

    for day in range(1, 11):
        winner = (day - 1) % 3
        for i in range(3):
            rows.append({
                "race_id": f"R{day:02d}",
                "race_date": f"2026-01-{day:02d}",
                "horse_name": horses[i],
                "jockey": jockeys[i],
                "trainer": f"T{i}",
                "finish_position": 1 if i == winner else i + 2,
                "distance_m": 1400 + (day % 3) * 200,
                "post_position": i + 1,
                "age": 3 + (i % 2),
                "carried_weight": 54 + i,
                "horse_weight": 460 + i * 10,
                "horse_weight_delta": (day + i) % 5 - 2,
                "win_odds": 2.5 + i,
            })

    feature_result = build_pre_race_features(pd.DataFrame(rows))
    oos = generate_walk_forward_predictions(
        feature_result.frame,
        feature_result.feature_columns,
        min_train_dates=4,
        test_dates=2,
    )

    assert oos.fold_count > 0
    assert not oos.predictions.empty
    sums = (
        oos.predictions
        .groupby("race_id")["predicted_win_probability"]
        .sum()
    )
    assert (sums.sub(1.0).abs() < 1e-9).all()
    assert (
        pd.to_datetime(oos.predictions["train_end"])
        < pd.to_datetime(oos.predictions["test_start"])
    ).all()
