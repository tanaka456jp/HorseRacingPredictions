from dataclasses import dataclass
import math
import pandas as pd


@dataclass(frozen=True)
class ForwardRuleDecision:
    target_fold: int
    selected_min_ev: float | None
    prior_rows: int
    prior_bets: int
    prior_flat_roi: float
    target_bets: int
    target_flat_roi: float


def _ensure_columns(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "fold_number",
        "predicted_win_probability",
        "decimal_odds",
        "finish_position",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(
            f"missing strategy-selection columns: {sorted(missing)}"
        )

    out = frame.copy()
    out["fold_number"] = pd.to_numeric(
        out["fold_number"], errors="raise"
    ).astype(int)
    out["predicted_win_probability"] = pd.to_numeric(
        out["predicted_win_probability"], errors="coerce"
    )
    out["decimal_odds"] = pd.to_numeric(
        out["decimal_odds"], errors="coerce"
    )
    out["finish_position"] = pd.to_numeric(
        out["finish_position"], errors="coerce"
    )
    out = out[
        out["predicted_win_probability"].notna()
        & out["decimal_odds"].gt(1.0)
        & out["finish_position"].notna()
    ].copy()
    out["ev"] = (
        out["predicted_win_probability"] * out["decimal_odds"]
    )
    out["is_winner"] = out["finish_position"].eq(1)
    out["flat_return_multiple"] = out["decimal_odds"].where(
        out["is_winner"],
        0.0,
    )
    return out


def _flat_roi(frame: pd.DataFrame) -> float:
    if frame.empty:
        return float("nan")
    return float(frame["flat_return_multiple"].mean() - 1.0)


def _select_threshold(
    prior: pd.DataFrame,
    candidate_thresholds: tuple[float, ...],
    min_prior_bets: int,
    require_positive_prior_roi: bool,
) -> tuple[float | None, int, float]:
    best_threshold = None
    best_bets = 0
    best_roi = 0.0 if require_positive_prior_roi else -math.inf

    for threshold in candidate_thresholds:
        selected = prior.loc[prior["ev"] >= threshold]
        bets = int(len(selected))
        if bets < min_prior_bets:
            continue
        roi = _flat_roi(selected)
        if not math.isfinite(roi):
            continue

        if roi > best_roi + 1e-12:
            best_threshold = float(threshold)
            best_bets = bets
            best_roi = roi
        elif (
            abs(roi - best_roi) <= 1e-12
            and best_threshold is not None
            and threshold < best_threshold
        ):
            best_threshold = float(threshold)
            best_bets = bets

    return best_threshold, best_bets, float(best_roi)


def forward_select_ev_threshold(
    predictions: pd.DataFrame,
    candidate_thresholds: tuple[float, ...] = (
        1.05, 1.10, 1.15, 1.20, 1.25,
        1.30, 1.40, 1.50, 1.75, 2.0,
    ),
    min_history_folds: int = 3,
    min_prior_bets: int = 200,
    require_positive_prior_roi: bool = True,
) -> tuple[pd.DataFrame, list[ForwardRuleDecision]]:
    if min_history_folds < 1:
        raise ValueError("min_history_folds must be positive")
    if min_prior_bets < 1:
        raise ValueError("min_prior_bets must be positive")
    if not candidate_thresholds:
        raise ValueError("candidate_thresholds must not be empty")
    if any(t <= 0 for t in candidate_thresholds):
        raise ValueError("candidate thresholds must be positive")

    data = _ensure_columns(predictions)
    folds = sorted(data["fold_number"].unique())
    decisions: list[ForwardRuleDecision] = []
    selected_target_rows = []

    for position, target_fold in enumerate(folds):
        if position < min_history_folds:
            continue

        prior_folds = set(folds[:position])
        prior = data.loc[data["fold_number"].isin(prior_folds)]
        target = data.loc[
            data["fold_number"] == target_fold
        ].copy()

        threshold, prior_bets, prior_roi = _select_threshold(
            prior,
            tuple(sorted(set(float(t) for t in candidate_thresholds))),
            min_prior_bets,
            require_positive_prior_roi,
        )

        target["selected_min_ev"] = threshold
        target["strategy_selected"] = (
            False
            if threshold is None
            else target["ev"].ge(threshold)
        )

        chosen = target.loc[target["strategy_selected"]]
        target_bets = int(len(chosen))
        target_roi = _flat_roi(chosen)

        decisions.append(
            ForwardRuleDecision(
                target_fold=int(target_fold),
                selected_min_ev=threshold,
                prior_rows=int(len(prior)),
                prior_bets=int(prior_bets),
                prior_flat_roi=float(prior_roi),
                target_bets=target_bets,
                target_flat_roi=float(target_roi),
            )
        )
        selected_target_rows.append(target)

    if not selected_target_rows:
        return pd.DataFrame(), decisions

    return pd.concat(selected_target_rows, ignore_index=True), decisions


def summarize_forward_selection(
    selected_rows: pd.DataFrame,
) -> dict:
    if selected_rows.empty:
        return {
            "evaluated_rows": 0,
            "bets": 0,
            "flat_roi": 0.0,
            "abstain_rate": 1.0,
        }

    bets = selected_rows.loc[selected_rows["strategy_selected"]]
    evaluated_folds = int(
        selected_rows["fold_number"].nunique()
    )
    active_folds = (
        int(bets["fold_number"].nunique())
        if not bets.empty
        else 0
    )

    return {
        "evaluated_rows": int(len(selected_rows)),
        "bets": int(len(bets)),
        "flat_roi": (
            _flat_roi(bets)
            if not bets.empty
            else 0.0
        ),
        "evaluated_folds": evaluated_folds,
        "active_folds": active_folds,
        "abstain_rate": (
            1.0 - active_folds / evaluated_folds
            if evaluated_folds
            else 1.0
        ),
    }
