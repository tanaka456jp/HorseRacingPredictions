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
        raw = self.pipeline.predict_proba(frame[self.feature_columns])[:, 1]
        raw = pd.Series(np.clip(raw, 1e-9, None), index=frame.index, dtype=float)
        totals = raw.groupby(frame[race_col]).transform("sum")
        normalized = raw / totals.replace(0, np.nan)
        return normalized.fillna(0.0)
