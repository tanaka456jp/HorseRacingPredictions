"""Research-only Phase 11: zero-mean, within-race longshot residuals."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .feature_window import align_history_to_training_start
from .features import build_pre_race_features
from .market_aware_ranker_v11 import MARKET_CONTEXT_FEATURES, add_market_context_features
from .exotic_top3_research import (
    TOP3_LONGSHOT_ODDS_MIN, Top3ProbabilityModel,
    add_top3_race_interaction_features, top3_outcomes,
)
from .exotic_longshot_phase7 import add_longshot_intrusion_features
from .exotic_longshot_phase9 import (
    LongshotResidualRegressor, _build_oof_residual_training, _evaluate_period,
)
from .exotic_longshot_phase10 import ROLLING_RESIDUAL_OOF_YEARS, _period_passed


def canonicalize_phase11_race_ids(frame: pd.DataFrame) -> pd.DataFrame:
    """Use calendar day plus source race ID for every Phase 11 race grouping.

    Older feature, overlay, and bootstrap helpers group by race_id alone.
    Work on a Phase 11 copy, leaving historical source data unchanged.
    """
    if "race_id" not in frame.columns or "race_date" not in frame.columns:
        raise ValueError("Phase 11 requires race_id and race_date")
    source_ids = frame["race_id"].astype("string")
    if source_ids.isna().any() or source_ids.str.strip().eq("").any():
        raise ValueError("Phase 11 race_id contains missing/blank values")
    dates = pd.to_datetime(frame["race_date"], errors="raise")
    if dates.isna().any():
        raise ValueError("Phase 11 race_date contains missing values")
    out = frame.copy()
    out["race_id"] = dates.dt.strftime("%Y-%m-%d") + ":" + source_ids
    return out


def center_residual_within_race(frame: pd.DataFrame, raw: pd.Series) -> pd.Series:
    """Remove only a race-common residual offset; never inspect outcomes."""
    if not frame.index.equals(raw.index):
        raise ValueError("residual index does not match candidates")
    if "race_id" not in frame.columns:
        raise ValueError("race_id missing")
    if "race_date" not in frame.columns:
        raise ValueError("race_date missing")
    if frame["race_id"].isna().any():
        raise ValueError("race_id contains missing values")
    race_dates = pd.to_datetime(frame["race_date"], errors="raise")
    if race_dates.isna().any():
        raise ValueError("race_date contains missing values")
    if not frame.index.is_unique:
        raise ValueError("candidate index must be unique")
    values = pd.to_numeric(raw, errors="raise").astype(float)
    if not bool(np.isfinite(values.to_numpy()).all()):
        raise ValueError("non-finite residual")
    race_keys = [race_dates.dt.normalize(), frame["race_id"]]
    return values - values.groupby(race_keys, sort=False).transform("mean")


class RaceCenteredResidualRegressor(LongshotResidualRegressor):
    def predict_residual(self, frame: pd.DataFrame) -> pd.Series:
        return center_residual_within_race(
            frame, super().predict_residual(frame)
        )


def evaluate_longshot_race_centered_phase11(
    history: pd.DataFrame,
    *,
    train_start: str = "2017-01-01",
    evaluation_2023_start: str = "2023-01-01",
    evaluation_2023_end: str = "2023-12-31",
    evaluation_2024_start: str = "2024-01-01",
    evaluation_2024_end: str = "2024-12-31",
) -> dict:
    start = pd.Timestamp(train_start).normalize()
    v23s, v23e, v24s, v24e = (
        pd.Timestamp(x).normalize() for x in (
            evaluation_2023_start, evaluation_2023_end,
            evaluation_2024_start, evaluation_2024_end,
        )
    )
    if not (start < v23s <= v23e < v24s <= v24e):
        raise ValueError("invalid Phase 11 development split")
    if (v23s, v23e, v24s, v24e) != (
        pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"),
        pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"),
    ):
        raise ValueError("Phase 11 development windows are frozen to 2023/2024")
    # Fail before feature engineering or model fitting if an isolated snapshot
    # contains final-holdout rows by mistake. No post-2024 rows may be used.
    if "race_date" not in history.columns:
        raise ValueError("Phase 11 history has no race_date")
    input_dates = pd.to_datetime(history["race_date"], errors="raise")
    if input_dates.isna().any() or input_dates.gt(v24e).any():
        raise ValueError("Phase 11 refuses missing or post-2024 race dates")
    data = align_history_to_training_start(
        history, train_start=str(start.date())
    )
    data["race_date"] = pd.to_datetime(data["race_date"], errors="raise")
    data["finish_position"] = pd.to_numeric(
        data["finish_position"], errors="coerce"
    )
    data["win_odds"] = pd.to_numeric(data["win_odds"], errors="coerce")
    data = data.loc[
        data["race_date"].le(v24e)
        & data["finish_position"].notna()
        & data["win_odds"].gt(1.0)
    ].copy()
    # Canonicalize before race-size eligibility, features, and bootstrap.
    data = canonicalize_phase11_race_ids(data)
    data = data.loc[
        data.groupby("race_id")["race_id"].transform("size").ge(3)
    ].copy()
    if data.empty:
        raise ValueError("Phase 11 history empty")

    enhanced = build_pre_race_features(
        data, experimental_ranker_v10=True
    )
    market = add_market_context_features(enhanced.frame)
    general, interactions = add_top3_race_interaction_features(market)
    specialist, intrusion = add_longshot_intrusion_features(general)
    general_features = (
        tuple(enhanced.feature_columns)
        + MARKET_CONTEXT_FEATURES + interactions
    )
    specialist_features = general_features + intrusion
    oof_frame, oof_target, residual_features, folds = (
        _build_oof_residual_training(
            general, specialist, general_features, specialist_features,
            oof_years=ROLLING_RESIDUAL_OOF_YEARS,
        )
    )
    dates = pd.to_datetime(general["race_date"], errors="raise")
    oof_dates = pd.to_datetime(oof_frame["race_date"], errors="raise")
    longshots = pd.to_numeric(
        general["win_odds"], errors="coerce"
    ).ge(TOP3_LONGSHOT_ODDS_MIN)

    periods, training = {}, {}
    for year, lower, upper in ((2023, v23s, v23e), (2024, v24s, v24e)):
        cutoff = pd.Timestamp(f"{year - 1}-12-31")
        train = general.loc[dates.le(cutoff)].copy()
        oof_train = oof_frame.loc[oof_dates.le(cutoff)].copy()
        oof_y = oof_target.loc[oof_train.index].copy()
        mask = dates.between(lower, upper, inclusive="both") & longshots
        eval_general = general.loc[mask].copy()
        eval_specialist = specialist.loc[mask].copy()
        if train.empty or oof_train.empty or eval_general.empty:
            raise ValueError(f"Phase 11 {year} empty split")
        base = Top3ProbabilityModel(
            list(general_features), iterations=300, depth=7,
            learning_rate=0.05, random_seed=42,
        ).fit(train, top3_outcomes(train))
        residual = RaceCenteredResidualRegressor(
            list(residual_features)
        ).fit(oof_train, oof_y)
        periods[str(year)] = _evaluate_period(
            eval_general, eval_specialist, base, residual, residual_features,
        )
        training[str(year)] = {
            "baseline_training_through": str(cutoff.date()),
            "baseline_training_rows": int(len(train)),
            "residual_training_through": str(cutoff.date()),
            "residual_training_rows": int(len(oof_train)),
            "residual_oof_years": sorted(
                int(y) for y in oof_dates.loc[oof_train.index].dt.year.unique()
            ),
        }
    gate = all(_period_passed(periods[y]) for y in ("2023", "2024"))
    return {
        "status": "research_only_longshot_race_centered_phase11",
        "hypothesis": (
            "Race-common residual offsets degrade calibration; "
            "subtract within-race longshot residual mean without tuning."
        ),
        "warning": (
            "Historical final odds are development-only; not pre-race "
            "odds. No trio/trifecta EV, staking, or real tickets."
        ),
        "oof_training": {
            "years": list(ROLLING_RESIDUAL_OOF_YEARS),
            "rows": int(len(oof_frame)), "folds": folds,
        },
        "annual_training": training,
        "research_protocol": {
            "correction": "fixed zero-mean residual per race among longshots",
            "evaluation": "annual rolling OOF, 2023/2024 only",
            "minimum_improvement_support": 0.8,
            "final_holdout": "2025-2026 untouched",
            "forward_paper": "unchanged",
            "paid_data": "not_used",
            "real_ticket_generation": "disabled",
        },
        "evaluation_2023": periods["2023"],
        "evaluation_2024": periods["2024"],
        "development_longshot_race_centered_gate_passed": gate,
    }
