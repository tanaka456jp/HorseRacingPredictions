import pandas as pd

from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.modeling import BaselineProbabilityModel

def test_pre_race_context_categories_are_features():
    frame = pd.DataFrame([
        {
            "race_id": "R1", "race_date": "2026-01-01",
            "horse_name": "A", "finish_position": 1,
            "distance_m": 1600, "post_position": 1, "age": 3,
            "carried_weight": 55, "horse_weight": 470,
            "horse_weight_delta": 0, "racecourse": "Kyoto",
            "surface": "Turf", "weather": "Fine",
            "track_condition": "Good", "sex": "M",
        },
        {
            "race_id": "R1", "race_date": "2026-01-01",
            "horse_name": "B", "finish_position": 2,
            "distance_m": 1600, "post_position": 2, "age": 3,
            "carried_weight": 55, "horse_weight": 480,
            "horse_weight_delta": 2, "racecourse": "Kyoto",
            "surface": "Turf", "weather": "Fine",
            "track_condition": "Good", "sex": "F",
        },
    ])
    result = build_pre_race_features(frame)
    for column in (
        "racecourse", "surface", "weather", "track_condition", "sex"
    ):
        assert column in result.feature_columns

def test_model_handles_unseen_category_at_prediction_time():
    train = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "distance_m": [1600, 1600, 1800, 1800],
        "surface": ["Turf", "Turf", "Dirt", "Dirt"],
        "is_winner": [1, 0, 0, 1],
    })
    test = pd.DataFrame({
        "race_id": ["R3", "R3"],
        "distance_m": [2000, 2000],
        "surface": ["Turf", "Synthetic"],
    })
    model = BaselineProbabilityModel(
        ["distance_m", "surface"]
    ).fit(train)
    probability = model.predict_win_probability(test)
    assert len(probability) == 2
    assert abs(probability.sum() - 1.0) < 1e-9
