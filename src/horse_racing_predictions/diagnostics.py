import math
import pandas as pd


def _safe_float(value):
    if pd.isna(value):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def add_research_diagnostic_columns(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "race_id",
        "predicted_win_probability",
        "decimal_odds",
        "finish_position",
        "confidence",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing diagnostic columns: {sorted(missing)}")

    out = frame.copy()
    out["decimal_odds"] = pd.to_numeric(
        out["decimal_odds"], errors="coerce"
    )
    out["predicted_win_probability"] = pd.to_numeric(
        out["predicted_win_probability"], errors="coerce"
    )
    out["is_winner"] = (
        pd.to_numeric(out["finish_position"], errors="coerce")
        .eq(1)
        .astype(int)
    )

    inverse = 1.0 / out["decimal_odds"].where(out["decimal_odds"] > 1.0)
    denominator = inverse.groupby(out["race_id"]).transform("sum")
    out["market_implied_probability"] = (
        inverse / denominator.replace(0, pd.NA)
    ).fillna(0.0)

    out["ev"] = (
        out["predicted_win_probability"] * out["decimal_odds"]
    )
    out["model_minus_market"] = (
        out["predicted_win_probability"]
        - out["market_implied_probability"]
    )
    market = out["market_implied_probability"].replace(0, pd.NA)
    out["model_to_market_ratio"] = (
        out["predicted_win_probability"] / market
    )
    out["realized_return_multiple"] = out["decimal_odds"].where(
        out["is_winner"].eq(1),
        0.0,
    )
    return out


def _band_report(
    frame: pd.DataFrame,
    column: str,
    bins: list[float],
    labels: list[str],
) -> list[dict]:
    band = pd.cut(
        frame[column],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True,
    )
    rows = []
    for label in labels:
        group = frame.loc[band == label]
        if group.empty:
            continue

        count = int(len(group))
        wins = int(group["is_winner"].sum())
        predicted = float(group["predicted_win_probability"].mean())
        actual = wins / count
        flat_return = float(group["realized_return_multiple"].mean())

        rows.append({
            "band": label,
            "rows": count,
            "wins": wins,
            "predicted_win_probability_mean": _safe_float(predicted),
            "actual_win_rate": _safe_float(actual),
            "calibration_error_actual_minus_predicted": _safe_float(
                actual - predicted
            ),
            "average_odds": _safe_float(group["decimal_odds"].mean()),
            "average_ev": _safe_float(group["ev"].mean()),
            "flat_bet_return_multiple": _safe_float(flat_return),
            "flat_bet_roi": _safe_float(flat_return - 1.0),
        })
    return rows


def _threshold_report(
    frame: pd.DataFrame,
    thresholds: list[float],
) -> list[dict]:
    rows = []
    for threshold in thresholds:
        group = frame.loc[frame["ev"] >= threshold]
        if group.empty:
            continue
        count = int(len(group))
        wins = int(group["is_winner"].sum())
        flat_return = float(group["realized_return_multiple"].mean())
        rows.append({
            "ev_threshold": threshold,
            "rows": count,
            "wins": wins,
            "hit_rate": _safe_float(wins / count),
            "average_model_probability": _safe_float(
                group["predicted_win_probability"].mean()
            ),
            "average_odds": _safe_float(group["decimal_odds"].mean()),
            "average_ev": _safe_float(group["ev"].mean()),
            "flat_bet_return_multiple": _safe_float(flat_return),
            "flat_bet_roi": _safe_float(flat_return - 1.0),
        })
    return rows


def build_oos_diagnostics(frame: pd.DataFrame) -> dict:
    data = add_research_diagnostic_columns(frame)

    finite = data[
        data["decimal_odds"].gt(1.0)
        & data["predicted_win_probability"].notna()
    ].copy()

    return {
        "status": "post_hoc_research_diagnostic_only",
        "warning": (
            "These segment and threshold results use the same OOS prediction "
            "set for diagnosis. They must not be used as a claimed validated "
            "strategy until selection rules are chosen on prior data and "
            "tested on later unseen folds."
        ),
        "rows": int(len(finite)),
        "ev_bands": _band_report(
            finite,
            "ev",
            [0.0, 0.8, 1.0, 1.05, 1.10, 1.15, 1.25, 1.50, 2.0, 3.0, math.inf],
            [
                "<0.80", "0.80-1.00", "1.00-1.05", "1.05-1.10",
                "1.10-1.15", "1.15-1.25", "1.25-1.50",
                "1.50-2.00", "2.00-3.00", ">=3.00",
            ],
        ),
        "odds_bands": _band_report(
            finite,
            "decimal_odds",
            [1.0, 2.0, 3.0, 5.0, 10.0, 20.0, 50.0, 100.0, math.inf],
            [
                "1-2", "2-3", "3-5", "5-10",
                "10-20", "20-50", "50-100", ">=100",
            ],
        ),
        "confidence_bands": _band_report(
            finite,
            "confidence",
            [0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.000001],
            [
                "<0.02", "0.02-0.05", "0.05-0.10", "0.10-0.20",
                "0.20-0.35", "0.35-0.50", ">=0.50",
            ],
        ),
        "model_minus_market_bands": _band_report(
            finite,
            "model_minus_market",
            [-math.inf, -0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, math.inf],
            [
                "<-0.10", "-0.10--0.05", "-0.05--0.02", "-0.02-0",
                "0-0.02", "0.02-0.05", "0.05-0.10", ">=0.10",
            ],
        ),
        "ev_threshold_sweep": _threshold_report(
            finite,
            [1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.40, 1.50, 1.75, 2.0, 2.5, 3.0],
        ),
    }
