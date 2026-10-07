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
from .exotic_top3_research import (
    TOP3_BOOTSTRAP_SAMPLES,
    TOP3_BOOTSTRAP_SEED,
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    paired_race_bootstrap_binary_quality,
    top3_outcomes,
)
from .exotic_longshot_phase7 import (
    add_longshot_intrusion_features,
)
from .exotic_longshot_phase8 import (
    _ranking_evidence,
    paired_race_bootstrap_longshot_ranking,
)


RESIDUAL_OOF_YEARS = (
    2018,
    2019,
    2020,
    2021,
    2022,
)
LONGSHOT_RESIDUAL_ITERATIONS = 250
LONGSHOT_RESIDUAL_DEPTH = 6
LONGSHOT_RESIDUAL_LEARNING_RATE = 0.03
LONGSHOT_RESIDUAL_RANDOM_SEED = 42


def _safe_float(value) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def annual_oof_masks(
    dates: pd.Series,
    year: int,
) -> tuple[pd.Series, pd.Series]:
    normalized = pd.to_datetime(
        dates,
        errors="raise",
    )
    start = pd.Timestamp(
        f"{int(year)}-01-01"
    )
    end = pd.Timestamp(
        f"{int(year)}-12-31"
    )
    train = normalized.lt(start)
    validation = normalized.between(
        start,
        end,
        inclusive="both",
    )
    if bool(
        (train & validation).any()
    ):
        raise ValueError(
            "OOF train/validation masks overlap"
        )
    return train, validation


def add_residual_overlay_features(
    frame: pd.DataFrame,
    baseline_probability: pd.Series,
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    if not baseline_probability.index.equals(
        frame.index
    ):
        raise ValueError(
            "baseline probability index differs from residual frame"
        )
    required = {
        "race_id",
        "market_implied_probability",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"residual overlay frame missing columns: {sorted(missing)}"
        )

    out = frame.copy()
    baseline = baseline_probability.astype(
        float
    ).clip(
        lower=1e-12,
        upper=1.0 - 1e-12,
    )
    market = pd.to_numeric(
        out["market_implied_probability"],
        errors="coerce",
    ).astype(float).clip(
        lower=1e-12,
        upper=1.0,
    )

    out[
        "residual_baseline_top3_probability"
    ] = baseline
    out[
        "residual_baseline_minus_market_probability"
    ] = baseline - market
    out[
        "residual_baseline_to_market_ratio"
    ] = (
        baseline / market
    ).clip(
        lower=0.0,
        upper=20.0,
    )

    race_mean = baseline.groupby(
        out["race_id"],
        sort=False,
    ).transform("mean")
    out[
        "residual_baseline_vs_longshot_race_mean"
    ] = baseline - race_mean

    rank = baseline.groupby(
        out["race_id"],
        sort=False,
    ).rank(
        method="average",
        ascending=False,
    )
    count = out["race_id"].groupby(
        out["race_id"],
        sort=False,
    ).transform("size")
    out[
        "residual_baseline_longshot_rank_pct"
    ] = rank / count.astype(float)

    generated = (
        "residual_baseline_top3_probability",
        "residual_baseline_minus_market_probability",
        "residual_baseline_to_market_ratio",
        "residual_baseline_vs_longshot_race_mean",
        "residual_baseline_longshot_rank_pct",
    )
    return out, generated


class LongshotResidualRegressor:
    def __init__(
        self,
        feature_columns: list[str],
        *,
        iterations: int = LONGSHOT_RESIDUAL_ITERATIONS,
        depth: int = LONGSHOT_RESIDUAL_DEPTH,
        learning_rate: float = LONGSHOT_RESIDUAL_LEARNING_RATE,
        random_seed: int = LONGSHOT_RESIDUAL_RANDOM_SEED,
    ) -> None:
        self.feature_columns = list(
            feature_columns
        )
        self.iterations = int(iterations)
        self.depth = int(depth)
        self.learning_rate = float(
            learning_rate
        )
        self.random_seed = int(
            random_seed
        )
        self.model = None
        self.categorical_columns: list[str] = []

    def _prepare(
        self,
        frame: pd.DataFrame,
    ) -> pd.DataFrame:
        out = frame[
            self.feature_columns
        ].copy()
        for column in self.feature_columns:
            if pd.api.types.is_numeric_dtype(
                out[column]
            ):
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
    ) -> "LongshotResidualRegressor":
        try:
            from catboost import CatBoostRegressor
        except ImportError as exc:
            raise RuntimeError(
                "Longshot residual research requires the research extra: "
                "pip install -e '.[research]'"
            ) from exc

        if len(frame) != len(target):
            raise ValueError(
                "residual target length must match training frame"
            )

        x = self._prepare(frame)
        self.categorical_columns = [
            column
            for column in self.feature_columns
            if not pd.api.types.is_numeric_dtype(
                x[column]
            )
        ]
        y = pd.to_numeric(
            target,
            errors="raise",
        ).astype(float)

        self.model = CatBoostRegressor(
            iterations=self.iterations,
            depth=self.depth,
            learning_rate=self.learning_rate,
            loss_function="RMSE",
            random_seed=self.random_seed,
            verbose=False,
            allow_writing_files=False,
            thread_count=-1,
            l2_leaf_reg=8.0,
        )
        self.model.fit(
            x,
            y,
            cat_features=self.categorical_columns,
        )
        return self

    def predict_residual(
        self,
        frame: pd.DataFrame,
    ) -> pd.Series:
        if self.model is None:
            raise RuntimeError(
                "longshot residual regressor is not fitted"
            )
        values = self.model.predict(
            self._prepare(frame)
        )
        return pd.Series(
            values,
            index=frame.index,
            dtype=float,
        ).clip(
            lower=-0.5,
            upper=0.5,
        )


def _quality(
    frame: pd.DataFrame,
    probability: pd.Series,
) -> dict:
    target = top3_outcomes(frame)
    return {
        "rows": int(len(frame)),
        "races": int(
            frame["race_id"].nunique()
        ),
        "top3_rate": _safe_float(
            target.mean()
        ),
        "binary_log_loss": _safe_float(
            binary_log_loss(
                probability,
                target,
            )
        ),
        "brier": _safe_float(
            brier_score(
                probability,
                target,
            )
        ),
        "average_probability": _safe_float(
            probability.mean()
        ),
    }


def _build_oof_residual_training(
    general_frame: pd.DataFrame,
    specialist_frame: pd.DataFrame,
    general_features: tuple[str, ...],
    specialist_base_features: tuple[str, ...],
    *,
    oof_years: tuple[int, ...] = RESIDUAL_OOF_YEARS,
) -> tuple[
    pd.DataFrame,
    pd.Series,
    tuple[str, ...],
    list[dict],
]:
    dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    longshot_mask = pd.to_numeric(
        general_frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)

    pieces: list[pd.DataFrame] = []
    targets: list[pd.Series] = []
    fold_evidence: list[dict] = []
    residual_feature_columns: (
        tuple[str, ...] | None
    ) = None

    for year in oof_years:
        train_mask, validation_mask = (
            annual_oof_masks(
                dates,
                year,
            )
        )
        train = general_frame.loc[
            train_mask
        ].copy()
        validation_general = (
            general_frame.loc[
                validation_mask
                & longshot_mask
            ].copy()
        )
        validation_specialist = (
            specialist_frame.loc[
                validation_mask
                & longshot_mask
            ].copy()
        )
        if (
            train.empty
            or validation_general.empty
            or validation_specialist.empty
        ):
            raise ValueError(
                f"OOF fold {year} has an empty train/validation period"
            )

        baseline_model = Top3ProbabilityModel(
            list(general_features),
            iterations=300,
            depth=7,
            learning_rate=0.05,
            random_seed=42,
        ).fit(
            train,
            top3_outcomes(train),
        )
        baseline_probability = (
            baseline_model.predict_probability(
                validation_general
            )
        )
        validation_specialist = (
            validation_specialist.loc[
                validation_general.index
            ].copy()
        )
        overlay, overlay_features = (
            add_residual_overlay_features(
                validation_specialist,
                baseline_probability,
            )
        )
        current_features = (
            tuple(
                specialist_base_features
            )
            + overlay_features
        )
        if residual_feature_columns is None:
            residual_feature_columns = (
                current_features
            )
        elif (
            tuple(
                residual_feature_columns
            )
            != tuple(current_features)
        ):
            raise ValueError(
                "residual OOF feature columns changed across folds"
            )

        target = (
            top3_outcomes(
                validation_general
            ).astype(float)
            - baseline_probability.astype(float)
        )
        pieces.append(overlay)
        targets.append(
            pd.Series(
                target.to_numpy(
                    dtype=float
                ),
                index=overlay.index,
                dtype=float,
            )
        )
        fold_evidence.append({
            "year": int(year),
            "training_rows": int(
                len(train)
            ),
            "training_races": int(
                train["race_id"].nunique()
            ),
            "validation_longshot_rows": int(
                len(validation_general)
            ),
            "validation_longshot_races": int(
                validation_general[
                    "race_id"
                ].nunique()
            ),
            "baseline_binary_log_loss": (
                _safe_float(
                    binary_log_loss(
                        baseline_probability,
                        top3_outcomes(
                            validation_general
                        ),
                    )
                )
            ),
            "baseline_brier": (
                _safe_float(
                    brier_score(
                        baseline_probability,
                        top3_outcomes(
                            validation_general
                        ),
                    )
                )
            ),
        })

    if residual_feature_columns is None:
        raise ValueError(
            "no residual OOF feature columns were produced"
        )

    training_frame = pd.concat(
        pieces,
        axis=0,
    ).sort_index()
    residual_target = pd.concat(
        targets,
        axis=0,
    ).reindex(
        training_frame.index
    )

    if residual_target.isna().any():
        raise ValueError(
            "residual OOF target contains missing values"
        )

    return (
        training_frame,
        residual_target,
        tuple(residual_feature_columns),
        fold_evidence,
    )


def _evaluate_period(
    general_frame: pd.DataFrame,
    specialist_frame: pd.DataFrame,
    baseline_model: Top3ProbabilityModel,
    residual_model: LongshotResidualRegressor,
    residual_feature_columns: tuple[str, ...],
) -> dict:
    baseline_probability = (
        baseline_model.predict_probability(
            general_frame
        )
    )
    overlay, overlay_features = (
        add_residual_overlay_features(
            specialist_frame.loc[
                general_frame.index
            ].copy(),
            baseline_probability,
        )
    )
    expected_features = (
        tuple(
            column
            for column in residual_feature_columns
            if not column.startswith(
                "residual_"
            )
        )
        + overlay_features
    )
    if (
        tuple(residual_feature_columns)
        != tuple(expected_features)
    ):
        raise ValueError(
            "residual evaluation feature columns changed"
        )

    predicted_residual = (
        residual_model.predict_residual(
            overlay
        )
    )
    corrected_probability = (
        baseline_probability
        + predicted_residual
    ).clip(
        lower=1e-6,
        upper=1.0 - 1e-6,
    )

    baseline_quality = _quality(
        general_frame,
        baseline_probability,
    )
    corrected_quality = _quality(
        general_frame,
        corrected_probability,
    )
    quality_bootstrap = (
        paired_race_bootstrap_binary_quality(
            general_frame,
            corrected_probability,
            baseline_probability,
        )
    )

    ranking = _ranking_evidence(
        general_frame,
        corrected_probability,
        baseline_probability,
    )
    ranking_bootstrap = (
        paired_race_bootstrap_longshot_ranking(
            ranking
        )
    )
    baseline_top1 = _safe_float(
        ranking[
            "baseline_top1_hit"
        ].mean()
    )
    corrected_top1 = _safe_float(
        ranking[
            "specialist_top1_hit"
        ].mean()
    )
    baseline_mrr = _safe_float(
        ranking[
            "baseline_mrr"
        ].mean()
    )
    corrected_mrr = _safe_float(
        ranking[
            "specialist_mrr"
        ].mean()
    )

    return {
        "period_start": str(
            general_frame[
                "race_date"
            ].min().date()
        ),
        "period_end": str(
            general_frame[
                "race_date"
            ].max().date()
        ),
        "definition": (
            "historical final win odds >= 6.0; "
            "development proxy only"
        ),
        "baseline": baseline_quality,
        "residual_corrected": (
            corrected_quality
        ),
        "binary_log_loss_delta": (
            _safe_float(
                float(
                    corrected_quality[
                        "binary_log_loss"
                    ]
                )
                - float(
                    baseline_quality[
                        "binary_log_loss"
                    ]
                )
            )
        ),
        "brier_delta": _safe_float(
            float(
                corrected_quality["brier"]
            )
            - float(
                baseline_quality["brier"]
            )
        ),
        "residual_prediction": {
            "mean": _safe_float(
                predicted_residual.mean()
            ),
            "std": _safe_float(
                predicted_residual.std(
                    ddof=0
                )
            ),
            "min": _safe_float(
                predicted_residual.min()
            ),
            "max": _safe_float(
                predicted_residual.max()
            ),
        },
        "top1": {
            "baseline_hit_rate": (
                baseline_top1
            ),
            "corrected_hit_rate": (
                corrected_top1
            ),
            "hit_rate_delta": _safe_float(
                float(corrected_top1)
                - float(baseline_top1)
            ),
        },
        "mrr": {
            "baseline": baseline_mrr,
            "corrected": corrected_mrr,
            "delta": _safe_float(
                float(corrected_mrr)
                - float(baseline_mrr)
            ),
        },
        "paired_bootstrap_quality": (
            quality_bootstrap
        ),
        "paired_bootstrap_ranking": (
            ranking_bootstrap
        ),
    }


def evaluate_longshot_residual_phase9(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    train_end: str = "2022-12-31",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    train_start_ts = pd.Timestamp(
        train_start
    ).normalize()
    train_end_ts = pd.Timestamp(
        train_end
    ).normalize()
    v23_start = pd.Timestamp(
        evaluation_2023_start
    ).normalize()
    v23_end = pd.Timestamp(
        evaluation_2023_end
    ).normalize()
    v24_start = pd.Timestamp(
        evaluation_2024_start
    ).normalize()
    v24_end = pd.Timestamp(
        evaluation_2024_end
    ).normalize()

    if not (
        train_start_ts
        <= train_end_ts
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError(
            "invalid longshot residual development split"
        )

    data = align_history_to_training_start(
        history,
        train_start=str(
            train_start_ts.date()
        ),
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
        raise ValueError(
            "longshot residual history is empty"
        )

    race_sizes = data.groupby(
        "race_id"
    )["race_id"].transform("size")
    data = data.loc[
        race_sizes.ge(3)
    ].copy()

    enhanced = build_pre_race_features(
        data,
        experimental_ranker_v10=True,
    )
    market_frame = add_market_context_features(
        enhanced.frame
    )
    general_frame, interaction_features = (
        add_top3_race_interaction_features(
            market_frame
        )
    )
    specialist_frame, intrusion_features = (
        add_longshot_intrusion_features(
            general_frame
        )
    )

    general_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES
        + interaction_features
    )
    specialist_base_features = (
        general_features
        + intrusion_features
    )

    (
        residual_training_frame,
        residual_target,
        residual_feature_columns,
        oof_folds,
    ) = _build_oof_residual_training(
        general_frame,
        specialist_frame,
        general_features,
        specialist_base_features,
    )

    residual_model = (
        LongshotResidualRegressor(
            list(
                residual_feature_columns
            )
        ).fit(
            residual_training_frame,
            residual_target,
        )
    )

    dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    final_train_mask = dates.le(
        train_end_ts
    )
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
    longshot_mask = pd.to_numeric(
        general_frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)

    final_train = general_frame.loc[
        final_train_mask
    ].copy()
    if final_train.empty:
        raise ValueError(
            "final baseline training frame is empty"
        )

    final_baseline_model = (
        Top3ProbabilityModel(
            list(general_features),
            iterations=300,
            depth=7,
            learning_rate=0.05,
            random_seed=42,
        ).fit(
            final_train,
            top3_outcomes(
                final_train
            ),
        )
    )

    v23_general = general_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v23_specialist = specialist_frame.loc[
        v23_mask & longshot_mask
    ].copy()
    v24_general = general_frame.loc[
        v24_mask & longshot_mask
    ].copy()
    v24_specialist = specialist_frame.loc[
        v24_mask & longshot_mask
    ].copy()
    if (
        v23_general.empty
        or v24_general.empty
    ):
        raise ValueError(
            "longshot residual evaluation period is empty"
        )

    result_2023 = _evaluate_period(
        v23_general,
        v23_specialist,
        final_baseline_model,
        residual_model,
        residual_feature_columns,
    )
    result_2024 = _evaluate_period(
        v24_general,
        v24_specialist,
        final_baseline_model,
        residual_model,
        residual_feature_columns,
    )

    def _period_passed(
        result: dict,
    ) -> bool:
        quality = result[
            "paired_bootstrap_quality"
        ]
        ranking = result[
            "paired_bootstrap_ranking"
        ]
        return bool(
            float(
                result[
                    "binary_log_loss_delta"
                ]
            ) < 0.0
            and float(
                result[
                    "brier_delta"
                ]
            ) < 0.0
            and float(
                result[
                    "top1"
                ][
                    "hit_rate_delta"
                ]
            ) > 0.0
            and float(
                result[
                    "mrr"
                ][
                    "delta"
                ]
            ) > 0.0
            and float(
                quality[
                    "binary_log_loss_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                quality[
                    "brier_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                ranking[
                    "top1_hit_rate_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
            and float(
                ranking[
                    "mrr_improvement_support"
                ]
            ) >= TOP3_MIN_IMPROVEMENT_SUPPORT
        )

    gate = bool(
        _period_passed(
            result_2023
        )
        and _period_passed(
            result_2024
        )
    )

    return {
        "status": (
            "research_only_longshot_residual_phase9"
        ),
        "hypothesis": (
            "The useful Phase 7 signal is an under/over-estimation residual "
            "around the calibrated general Top-3 model rather than a standalone "
            "probability or ranker. A residual regressor trained only on "
            "annual out-of-fold longshot examples can correct general Top-3 "
            "probabilities without in-sample stacking leakage."
        ),
        "warning": (
            "Historical final win odds remain a development-only longshot proxy. "
            "Phase 9 tests probability/ranking quality only and does not create "
            "trio/trifecta expected-value estimates or real betting tickets."
        ),
        "training": {
            "oof_years": list(
                RESIDUAL_OOF_YEARS
            ),
            "oof_longshot_rows": int(
                len(
                    residual_training_frame
                )
            ),
            "oof_longshot_races": int(
                residual_training_frame[
                    "race_id"
                ].nunique()
            ),
            "residual_target_mean": (
                _safe_float(
                    residual_target.mean()
                )
            ),
            "residual_target_std": (
                _safe_float(
                    residual_target.std(
                        ddof=0
                    )
                )
            ),
            "residual_iterations": (
                LONGSHOT_RESIDUAL_ITERATIONS
            ),
            "residual_depth": (
                LONGSHOT_RESIDUAL_DEPTH
            ),
            "residual_learning_rate": (
                LONGSHOT_RESIDUAL_LEARNING_RATE
            ),
            "residual_random_seed": (
                LONGSHOT_RESIDUAL_RANDOM_SEED
            ),
            "oof_folds": oof_folds,
        },
        "feature_design": {
            "general_feature_count": int(
                len(
                    general_features
                )
            ),
            "specialist_base_feature_count": int(
                len(
                    specialist_base_features
                )
            ),
            "residual_feature_count": int(
                len(
                    residual_feature_columns
                )
            ),
            "residual_overlay_features": [
                column
                for column in residual_feature_columns
                if column.startswith(
                    "residual_"
                )
            ],
        },
        "research_protocol": {
            "baseline": (
                "general Phase 2-style Top-3 model trained through 2022"
            ),
            "stacking_safety": (
                "residual training target uses annual out-of-fold baseline "
                "predictions for 2018-2022; no same-row in-sample baseline "
                "prediction is used as residual target"
            ),
            "correction": (
                "corrected_probability = clip(general_probability + "
                "predicted_residual, 1e-6, 1-1e-6); no blend weight tuning"
            ),
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
            ),
            "bootstrap_samples": (
                TOP3_BOOTSTRAP_SAMPLES
            ),
            "bootstrap_seed": (
                TOP3_BOOTSTRAP_SEED
            ),
            "final_holdout": (
                "2025-2026 untouched"
            ),
            "forward_paper": "unchanged",
            "paid_data": "not_used",
            "real_ticket_generation": "disabled",
        },
        "evaluation_2023": result_2023,
        "evaluation_2024": result_2024,
        "development_longshot_residual_gate_passed": gate,
    }
