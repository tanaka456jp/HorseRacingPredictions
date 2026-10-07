from __future__ import annotations

import pandas as pd

from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import (
    MARKET_CONTEXT_FEATURES,
    add_market_context_features,
)
from .exotic_top3_research import (
    TOP3_LONGSHOT_ODDS_MIN,
    TOP3_MIN_IMPROVEMENT_SUPPORT,
    Top3ProbabilityModel,
    add_top3_race_interaction_features,
    top3_outcomes,
)
from .exotic_longshot_phase7 import (
    add_longshot_intrusion_features,
)
from .exotic_longshot_phase9 import (
    LongshotResidualRegressor,
    _build_oof_residual_training,
    _evaluate_period,
)


ROLLING_RESIDUAL_OOF_YEARS = (
    2018,
    2019,
    2020,
    2021,
    2022,
    2023,
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


def evaluate_longshot_rolling_residual_phase10(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    train_start_ts = pd.Timestamp(
        train_start
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
        < v23_start
        <= v23_end
        < v24_start
        <= v24_end
    ):
        raise ValueError(
            "invalid rolling residual development split"
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
            "rolling residual history is empty"
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
        oof_training_frame,
        oof_residual_target,
        residual_feature_columns,
        oof_folds,
    ) = _build_oof_residual_training(
        general_frame,
        specialist_frame,
        general_features,
        specialist_base_features,
        oof_years=ROLLING_RESIDUAL_OOF_YEARS,
    )

    general_dates = pd.to_datetime(
        general_frame["race_date"],
        errors="raise",
    )
    oof_dates = pd.to_datetime(
        oof_training_frame["race_date"],
        errors="raise",
    )
    longshot_mask = pd.to_numeric(
        general_frame["win_odds"],
        errors="coerce",
    ).ge(TOP3_LONGSHOT_ODDS_MIN)

    def _fit_and_score(
        *,
        evaluation_year: int,
        evaluation_start: pd.Timestamp,
        evaluation_end: pd.Timestamp,
    ) -> tuple[dict, dict]:
        baseline_cutoff = pd.Timestamp(
            f"{evaluation_year - 1}-12-31"
        )
        residual_cutoff = baseline_cutoff

        baseline_train = general_frame.loc[
            general_dates.le(
                baseline_cutoff
            )
        ].copy()
        residual_mask = oof_dates.le(
            residual_cutoff
        )
        residual_train = (
            oof_training_frame.loc[
                residual_mask
            ].copy()
        )
        residual_target = (
            oof_residual_target.loc[
                residual_train.index
            ].copy()
        )

        evaluation_mask = (
            general_dates.between(
                evaluation_start,
                evaluation_end,
                inclusive="both",
            )
            & longshot_mask
        )
        evaluation_general = (
            general_frame.loc[
                evaluation_mask
            ].copy()
        )
        evaluation_specialist = (
            specialist_frame.loc[
                evaluation_mask
            ].copy()
        )

        if (
            baseline_train.empty
            or residual_train.empty
            or evaluation_general.empty
        ):
            raise ValueError(
                f"rolling residual year {evaluation_year} has an empty split"
            )

        baseline_model = (
            Top3ProbabilityModel(
                list(
                    general_features
                ),
                iterations=300,
                depth=7,
                learning_rate=0.05,
                random_seed=42,
            ).fit(
                baseline_train,
                top3_outcomes(
                    baseline_train
                ),
            )
        )
        residual_model = (
            LongshotResidualRegressor(
                list(
                    residual_feature_columns
                )
            ).fit(
                residual_train,
                residual_target,
            )
        )

        result = _evaluate_period(
            evaluation_general,
            evaluation_specialist,
            baseline_model,
            residual_model,
            residual_feature_columns,
        )
        training = {
            "evaluation_year": int(
                evaluation_year
            ),
            "baseline_training_through": str(
                baseline_cutoff.date()
            ),
            "baseline_training_rows": int(
                len(
                    baseline_train
                )
            ),
            "baseline_training_races": int(
                baseline_train[
                    "race_id"
                ].nunique()
            ),
            "residual_training_through": str(
                residual_cutoff.date()
            ),
            "residual_training_rows": int(
                len(
                    residual_train
                )
            ),
            "residual_training_races": int(
                residual_train[
                    "race_id"
                ].nunique()
            ),
            "residual_training_oof_years": sorted(
                int(year)
                for year in pd.to_datetime(
                    residual_train[
                        "race_date"
                    ]
                ).dt.year.unique()
            ),
        }
        return result, training

    result_2023, training_2023 = (
        _fit_and_score(
            evaluation_year=2023,
            evaluation_start=v23_start,
            evaluation_end=v23_end,
        )
    )
    result_2024, training_2024 = (
        _fit_and_score(
            evaluation_year=2024,
            evaluation_start=v24_start,
            evaluation_end=v24_end,
        )
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
            "research_only_longshot_rolling_residual_phase10"
        ),
        "hypothesis": (
            "Phase 9 improved all four metrics directionally in both years "
            "but weakened in 2024. The longshot residual relationship may "
            "drift over time. Annual walk-forward refitting of both the "
            "general Top-3 baseline and the OOF-trained residual overlay may "
            "preserve the residual signal without tuning its scale."
        ),
        "warning": (
            "Historical final win odds remain a development-only longshot proxy. "
            "Phase 10 is walk-forward probability/ranking research only and does "
            "not create trio/trifecta expected-value estimates or betting tickets."
        ),
        "oof_training": {
            "available_oof_years": list(
                ROLLING_RESIDUAL_OOF_YEARS
            ),
            "rows": int(
                len(
                    oof_training_frame
                )
            ),
            "races": int(
                oof_training_frame[
                    "race_id"
                ].nunique()
            ),
            "folds": oof_folds,
        },
        "annual_training": {
            "2023": training_2023,
            "2024": training_2024,
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
        },
        "research_protocol": {
            "2023": (
                "general baseline through 2022; residual overlay trained "
                "on annual OOF longshot residuals from 2018-2022"
            ),
            "2024": (
                "general baseline through 2023; residual overlay trained "
                "on annual OOF longshot residuals from 2018-2023, where "
                "the 2023 residual target was produced by a baseline "
                "trained only through 2022"
            ),
            "correction": (
                "same fixed Phase 9 residual model/settings and "
                "probability addition; no scale or threshold tuning"
            ),
            "minimum_improvement_support": (
                TOP3_MIN_IMPROVEMENT_SUPPORT
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
        "development_longshot_rolling_residual_gate_passed": gate,
    }
