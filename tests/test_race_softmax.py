import numpy as np
import pandas as pd

from horse_racing_predictions.modeling import BaselineProbabilityModel

class _FakePipeline:
    def decision_function(self, frame):
        return np.array([0.0, 1.0, 2.0, 0.0, 0.0], dtype=float)

def test_race_softmax_uses_decision_scores_and_normalizes_per_race():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R1", "R2", "R2"],
        "x": [0, 0, 0, 0, 0],
    })
    model = BaselineProbabilityModel(["x"])
    model.pipeline = _FakePipeline()

    p = model.predict_win_probability(frame)

    expected_r1 = np.exp([0.0, 1.0, 2.0])
    expected_r1 = expected_r1 / expected_r1.sum()
    assert np.allclose(p.iloc[:3].to_numpy(), expected_r1)
    assert np.allclose(p.iloc[3:].to_numpy(), [0.5, 0.5])
    assert np.isclose(p.groupby(frame["race_id"]).sum().iloc[0], 1.0)
    assert np.isclose(p.groupby(frame["race_id"]).sum().iloc[1], 1.0)
