from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

@dataclass
class BaselineProbabilityModel:
    feature_columns: list[str]

    def __post_init__(self):
        self.pipeline = None
        self.numeric_columns: list[str] = []
        self.categorical_columns: list[str] = []

    def _build_pipeline(self, frame: pd.DataFrame) -> Pipeline:
        numeric = []
        categorical = []
        for column in self.feature_columns:
            if pd.api.types.is_numeric_dtype(frame[column]):
                numeric.append(column)
            else:
                categorical.append(column)

        transformers = []
        if numeric:
            transformers.append((
                "numeric",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]),
                numeric,
            ))
        if categorical:
            transformers.append((
                "categorical",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore")),
                ]),
                categorical,
            ))

        self.numeric_columns = numeric
        self.categorical_columns = categorical

        preprocess = ColumnTransformer(
            transformers=transformers,
            remainder="drop",
        )
        return Pipeline([
            ("preprocess", preprocess),
            ("model", LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
            )),
        ])

    def fit(self, frame: pd.DataFrame, target_col: str = "is_winner"):
        self.pipeline = self._build_pipeline(frame)
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
        if self.pipeline is None:
            raise RuntimeError("model is not fitted")

        scores = np.asarray(
            self.pipeline.decision_function(frame[self.feature_columns]),
            dtype=float,
        )
        scores = pd.Series(scores, index=frame.index, dtype=float)

        race_max = scores.groupby(frame[race_col]).transform("max")
        exp_score = np.exp(scores - race_max)
        totals = exp_score.groupby(frame[race_col]).transform("sum")
        probability = exp_score / totals.replace(0, np.nan)
        return probability.fillna(0.0)
