from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

def _race_softmax(scores, race_ids, index):
    scores = pd.Series(
        np.asarray(scores, dtype=float),
        index=index,
        dtype=float,
    )
    race_max = scores.groupby(race_ids).transform("max")
    exp_score = np.exp(scores - race_max)
    totals = exp_score.groupby(race_ids).transform("sum")
    return (exp_score / totals.replace(0, np.nan)).fillna(0.0)

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
        scores = self.pipeline.decision_function(
            frame[self.feature_columns]
        )
        return _race_softmax(scores, frame[race_col], frame.index)

@dataclass
class CatBoostProbabilityModel:
    feature_columns: list[str]
    iterations: int = 350
    depth: int = 7
    learning_rate: float = 0.05
    random_seed: int = 42

    def __post_init__(self):
        self.model = None
        self.categorical_columns: list[str] = []

    def _prepare(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame[self.feature_columns].copy()
        for column in self.feature_columns:
            if pd.api.types.is_numeric_dtype(out[column]):
                out[column] = pd.to_numeric(
                    out[column],
                    errors="coerce",
                )
            else:
                out[column] = (
                    out[column]
                    .astype("string")
                    .fillna("UNKNOWN")
                    .astype(str)
                )
        return out

    def fit(self, frame: pd.DataFrame, target_col: str = "is_winner"):
        try:
            from catboost import CatBoostClassifier
        except ImportError as exc:
            raise RuntimeError(
                "CatBoost model requires the research extra: "
                "pip install -e '.[research]'"
            ) from exc

        x = self._prepare(frame)
        self.categorical_columns = [
            column for column in self.feature_columns
            if not pd.api.types.is_numeric_dtype(x[column])
        ]
        self.model = CatBoostClassifier(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            loss_function="Logloss",
            auto_class_weights="Balanced",
            random_seed=self.random_seed,
            verbose=False,
            allow_writing_files=False,
            thread_count=-1,
            l2_leaf_reg=5.0,
        )
        self.model.fit(
            x,
            frame[target_col].astype(int),
            cat_features=self.categorical_columns,
        )
        return self

    def predict_win_probability(
        self,
        frame: pd.DataFrame,
        race_col: str = "race_id",
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError("model is not fitted")
        x = self._prepare(frame)
        scores = self.model.predict(
            x,
            prediction_type="RawFormulaVal",
        )
        return _race_softmax(scores, frame[race_col], frame.index)
