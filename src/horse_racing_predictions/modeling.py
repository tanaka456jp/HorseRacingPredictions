from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

@dataclass
class BaselineProbabilityModel:
    feature_columns: list[str]

    def __post_init__(self):
        self.pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ])

    def fit(self, frame: pd.DataFrame, target_col: str = "is_winner"):
        self.pipeline.fit(
            frame[self.feature_columns],
            frame[target_col].astype(int),
        )
        return self

    def predict_win_probability(
        self,
        frame: pd.DataFrame,
        race_col: str = "race_id",
    ) -> pd.Series:
        scores = np.asarray(
            self.pipeline.decision_function(frame[self.feature_columns]),
            dtype=float,
        )
        scores = pd.Series(scores, index=frame.index, dtype=float)

        # Convert horse-level utility scores into a proper race-level
        # probability distribution.  Subtracting the race maximum keeps
        # exp() numerically stable without changing the softmax.
        race_max = scores.groupby(frame[race_col]).transform("max")
        exp_score = np.exp(scores - race_max)
        totals = exp_score.groupby(frame[race_col]).transform("sum")
        probability = exp_score / totals.replace(0, np.nan)
        return probability.fillna(0.0)
