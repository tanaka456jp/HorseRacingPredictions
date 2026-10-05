from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .evaluation import brier_score, binary_log_loss
from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)


TOP3_LONGSHOT_ODDS_MIN = 6.0

TOP3_INTERACTION_SOURCE_FEATURES = (
    "horse_recent_top3_rate_5",
    "horse_recent_finish_percentile_mean_5",
    "horse_recent_early_ratio_mean_5",
    "horse_recent_late_ratio_mean_5",
    "jockey_past_win_rate",
    "jockey_course_past_win_rate",
    "horse_jockey_past_win_rate",
    "trainer_past_win_rate",
)


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def top3_outcomes(frame: pd.DataFrame) -> pd.Series:
    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    return finish.le(3).astype(int)


def add_top3_race_interaction_features(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Add past-only runner-vs-field context without using same-race outcomes."""
    if "race_id" not in frame.columns:
        raise ValueError("race interaction features require race_id")

    out = frame.copy()
    generated: list[str] = []

    for source in TOP3_INTERACTION_SOURCE_FEATURES:
        if source not in out.columns:
            continue

        values = pd.to_numeric(
            out[source],
            errors="coerce",
        )
        race = values.groupby(out["race_id"], sort=False)
        mean_name = f"{source}_race_mean"
        delta_name = f"{source}_vs_race_mean"
        std_name = f"{source}_race_std"
        rank_name = f"{source}_race_rank_pct"

        race_mean = race.transform("mean")
        out[mean_name] = race_mean
        out[delta_name] = values - race_mean
        out[std_name] = race.transform("std").fillna(0.0)
        out[rank_name] = race.rank(
            method="average",
            ascending=False,
            pct=True,
        )

        generated.extend(
            [mean_name, delta_name, std_name, rank_name]
        )

    if "market_implied_probability" in out.columns:
        market = pd.to_numeric(
            out["market_implied_probability"],
            errors="coerce",
        ).clip(lower=1e-12, upper=1.0)
        grouped = market.groupby(out["race_id"], sort=False)

        out["market_favorite_probability"] = grouped.transform("max")
        out["market_probability_std"] = grouped.transform("std").fillna(0.0)

        entropy_by_race = (
            -(market * np.log(market))
            .groupby(out["race_id"], sort=False)
            .transform("sum")
        )
        out["market_race_entropy"] = entropy_by_race

        rank = market.groupby(
            out["race_id"],
            sort=False,
        ).rank(
            method="first",
            ascending=False,
        )
        top3_component = market.where(rank.le(3), 0.0)
        out["market_top3_probability_share"] = (
            top3_component.groupby(
                out["race_id"],
                sort=False,
            ).transform("sum")
        )

        generated.extend([
            "market_favorite_probability",
            "market_probability_std",
            "market_race_entropy",
            "market_top3_probability_share",
        ])

    return out, tuple(generated)


class Top3ProbabilityModel:
    def __init__(
        self,
        feature_columns: list[str],
        *,
        iterations: int = 300,
        depth: int = 7,
        learning_rate: float = 0.05,
        random_seed: int = 42,
    ) -> None:
        self.feature_columns = list(feature_columns)
        self.iterations = int(iterations)
        self.depth = int(depth)
        self.learning_rate = float(learning_rate)
        self.random_seed = int(random_seed)
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

    def fit(
        self,
        frame: pd.DataFrame,
        target: pd.Series,
    ) -> "Top3ProbabilityModel":
        try:
            from catboost import CatBoostClassifier
        except ImportError as exc:
            raise RuntimeError(
                "Top-3 research requires the research extra: "
                "pip install -e '.[research]'"
            ) from exc

        if len(frame) != len(target):
            raise ValueError(
                "top3 target length must match training frame"
            )

        x = self._prepare(frame)
        self.categorical_columns = [
            column
            for column in self.feature_columns
            if not pd.api.types.is_numeric_dtype(x[column])
        ]
        y = pd.to_numeric(
            target,
            errors="raise",
        ).astype(int)

        self.model = CatBoostClassifier(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            loss_function="Logloss",
            random_seed=self.random_seed,
            verbose=False,
            allow_writing_files=False,
            thread_count=-1,
            l2_leaf_reg=5.0,
        )
        self.model.fit(
            x,
            y,
            cat_features=self.categorical_columns,
        )
        return self

    def predict_probability(
        self,
        frame: pd.DataFrame,
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError("top3 probability model is not fitted")
        x = self._prepare(frame)
        values = self.model.predict_proba(x)[:, 1]
        return pd.Series(
            values,
            index=frame.index,
            dtype=float,
        ).clip(lower=1e-12, upper=1.0 - 1e-12)


def _top3_quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    target = top3_outcomes(frame)
    return {
        "rows": int(len(frame)),
        "races": int(frame["race_id"].nunique()),
        "top3_rate": _safe_float(target.mean()),
        "binary_log_loss": _safe_float(
            binary_log_loss(probability, target)
        ),
        "brier": _safe_float(
            brier_score(probability, target)
        ),
        "average_probability": _safe_float(
            probability.mean()
        ),
    }


def _evaluate_period(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
    challenger_probability: pd.Series,
) -> dict:
    baseline = _top3_quality(
        frame,
        baseline_probability,
    )
    challenger = _top3_quality(
        frame,
        challenger_probability,
    )

    longshot_mask = pd.to_numeric(
        frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)
    longshot = frame.loc[longshot_mask].copy()
    baseline_longshot_probability = (
        baseline_probability.loc[longshot.index]
    )
    challenger_longshot_probability = (
        challenger_probability.loc[longshot.index]
    )

    baseline_longshot = _top3_quality(
        longshot,
        baseline_longshot_probability,
    )
    challenger_longshot = _top3_quality(
        longshot,
        challenger_longshot_probability,
    )

    return {
        "period_start": str(frame["race_date"].min().date()),
        "period_end": str(frame["race_date"].max().date()),
        "baseline": baseline,
        "challenger": challenger,
        "binary_log_loss_delta": _safe_float(
            float(challenger["binary_log_loss"])
            - float(baseline["binary_log_loss"])
        ),
        "brier_delta": _safe_float(
            float(challenger["brier"])
            - float(baseline["brier"])
        ),
        "longshot_proxy": {
            "definition": (
                "historical final win odds >= 6.0; "
                "development proxy only"
            ),
            "baseline": baseline_longshot,
            "challenger": challenger_longshot,
            "binary_log_loss_delta": _safe_float(
                float(challenger_longshot["binary_log_loss"])
                - float(baseline_longshot["binary_log_loss"])
            ),
            "brier_delta": _safe_float(
                float(challenger_longshot["brier"])
                - float(baseline_longshot["brier"])
            ),
        },
    }


def evaluate_exotic_top3_development(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
    iterations: int = 300,
) -> dict:
    """Research whether runner-vs-field context improves Top-3 prediction."""
    if iterations < 1:
        raise ValueError("iterations must be positive")

    train_start_ts = pd.Timestamp(train_start).normalize()
    train_end_ts = pd.Timestamp(train_end).normalize()
    v23_start = pd.Timestamp(evaluation_2023_start).normalize()
    v23_end = pd.Timestamp(evaluation_2023_end).normalize()
    v24_start = pd.Timestamp(evaluation_2024_start).normalize()
    v24_end = pd.Timestamp(evaluation_2024_end).normalize()

    if not (
        train_start_ts
        <= train_end_ts
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError("invalid exotic top3 development time split")

    data = align_history_to_training_start(
        history,
        train_start=str(train_start_ts.date()),
    )
    data["race_date"] = pd.to_datetime(
        data["race_date"],
        errors="raise",
    )
    data["finish_position"] = pd.to_numeric(
        data["finish_position"],
        errors="coerce",
    )
    data["win_odds"] = pd.to_numeric(
        data["win_odds"],
        errors="coerce",
    )

    data = data.loc[
        data["finish_position"].notna()
        & data["win_odds"].gt(1.0)
        & data["race_date"].le(v24_end)
    ].copy()
    if data.empty:
        raise ValueError("exotic top3 development history is empty")

    race_sizes = data.groupby("race_id")["race_id"].transform("size")
    data = data.loc[race_sizes.ge(3)].copy()

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    baseline_frame = add_market_context_features(
        enhanced.frame
    )
    challenger_frame, interaction_features = (
        add_top3_race_interaction_features(
            baseline_frame
        )
    )

    baseline_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
    )
    challenger_features = (
        baseline_features
        + interaction_features
    )

    dates = pd.to_datetime(
        baseline_frame["race_date"],
        errors="raise",
    )
    train_mask = dates.le(train_end_ts)
    v23_mask = dates.between(
        v23_start,
        v23_end,
        inclusive="both",
    )
    v24_mask = dates.between(
        v24_start,
        v24_end,
        inclusive="both",
    )

    baseline_train = baseline_frame.loc[train_mask].copy()
    challenger_train = challenger_frame.loc[train_mask].copy()
    baseline_v23 = baseline_frame.loc[v23_mask].copy()
    challenger_v23 = challenger_frame.loc[v23_mask].copy()
    baseline_v24 = baseline_frame.loc[v24_mask].copy()
    challenger_v24 = challenger_frame.loc[v24_mask].copy()

    if (
        baseline_train.empty
        or baseline_v23.empty
        or baseline_v24.empty
    ):
        raise ValueError(
            "exotic top3 development split contains an empty period"
        )

    target = top3_outcomes(baseline_train)
    baseline_model = Top3ProbabilityModel(
        list(baseline_features),
        iterations=iterations,
    ).fit(
        baseline_train,
        target,
    )
    challenger_model = Top3ProbabilityModel(
        list(challenger_features),
        iterations=iterations,
    ).fit(
        challenger_train,
        target,
    )

    def _score(
        baseline_period: pd.DataFrame,
        challenger_period: pd.DataFrame,
    ) -> dict:
        baseline_probability = (
            baseline_model.predict_probability(
                baseline_period
            )
        )
        challenger_probability = (
            challenger_model.predict_probability(
                challenger_period
            )
        )
        return _evaluate_period(
            baseline_period,
            baseline_probability,
            challenger_probability,
        )

    result_2023 = _score(
        baseline_v23,
        challenger_v23,
    )
    result_2024 = _score(
        baseline_v24,
        challenger_v24,
    )

    def _period_passed(result: dict) -> bool:
        longshot = result["longshot_proxy"]
        return bool(
            float(result["binary_log_loss_delta"]) < 0.0
            and float(result["brier_delta"]) < 0.0
            and float(
                longshot["binary_log_loss_delta"]
            ) < 0.0
            and float(longshot["brier_delta"]) < 0.0
        )

    gate = bool(
        _period_passed(result_2023)
        and _period_passed(result_2024)
    )

    return {
        "status": "research_only_exotic_top3_development",
        "hypothesis": (
            "Past-only runner-vs-field composition features improve "
            "Top-3 probability estimation, including the pre-registered "
            "historical final-odds >= 6.0 longshot proxy."
        ),
        "warning": (
            "This phase does not estimate trifecta/trio expected value. "
            "Historical final win odds are used only for development "
            "segmentation. No exotic combination odds are available in "
            "the current free pipeline, so no three-leg bet is selected."
        ),
        "training": {
            "period_start": str(
                baseline_train["race_date"].min().date()
            ),
            "period_end": str(
                baseline_train["race_date"].max().date()
            ),
            "rows": int(len(baseline_train)),
            "races": int(
                baseline_train["race_id"].nunique()
            ),
            "top3_rate": _safe_float(target.mean()),
        },
        "feature_design": {
            "baseline_feature_count": int(
                len(baseline_features)
            ),
            "challenger_feature_count": int(
                len(challenger_features)
            ),
            "interaction_sources_requested": list(
                TOP3_INTERACTION_SOURCE_FEATURES
            ),
            "interaction_features_generated": list(
                interaction_features
            ),
            "pedigree_status": (
                "not_enabled: current history exposes only a blood "
                "registration identifier, not semantic sire/dam/"
                "broodmare-sire fields; identifier memorization is "
                "intentionally excluded"
            ),
        },
        "research_protocol": {
            "development_periods": [
                "training_through_2022",
                "2023_development_reused",
                "2024_development_reused",
            ],
            "final_holdout": "2025-2026 untouched",
            "forward_paper": "unchanged",
            "paid_data": "not_used",
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_gate_passed": gate,
    }
