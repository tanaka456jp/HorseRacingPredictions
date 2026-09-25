import pandas as pd

from horse_racing_predictions.modeling import BaselineProbabilityModel
from horse_racing_predictions.walkforward import expanding_walk_forward_splits

def test_walk_forward_never_uses_future():
    df = pd.DataFrame({
        "race_date": pd.date_range("2026-01-01", periods=10, freq="D"),
        "x": range(10),
    })
    folds = list(
        expanding_walk_forward_splits(
            df,
            "race_date",
            min_train_dates=4,
            test_dates=2,
        )
    )
    assert folds
    for fold in folds:
        train_max = pd.to_datetime(df.loc[fold.train_index, "race_date"]).max()
        test_min = pd.to_datetime(df.loc[fold.test_index, "race_date"]).min()
        assert train_max < test_min

def test_race_probabilities_sum_to_one():
    rows = []
    for race_no in range(20):
        for horse_no in range(4):
            rows.append({
                "race_id": f"R{race_no}",
                "speed": float(horse_no + race_no % 3),
                "weight_delta": float(horse_no - 2),
                "is_winner": 1 if horse_no == (race_no % 4) else 0,
            })
    df = pd.DataFrame(rows)

    model = BaselineProbabilityModel(
        ["speed", "weight_delta"]
    ).fit(df)

    p = model.predict_win_probability(df)
    sums = p.groupby(df["race_id"]).sum()

    assert (sums.sub(1.0).abs() < 1e-9).all()
    assert ((p >= 0) & (p <= 1)).all()
