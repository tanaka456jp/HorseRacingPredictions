from __future__ import annotations

import pandas as pd


def align_history_to_training_start(
    history: pd.DataFrame,
    *,
    train_start: str | pd.Timestamp,
) -> pd.DataFrame:
    if history.empty:
        raise ValueError("history is empty")
    if "race_date" not in history.columns:
        raise ValueError("history lacks race_date")

    data = history.copy()
    data["race_date"] = pd.to_datetime(
        data["race_date"],
        errors="raise",
    )
    start = pd.Timestamp(train_start).normalize()
    aligned = data.loc[
        data["race_date"].dt.normalize() >= start
    ].copy()
    if aligned.empty:
        raise ValueError(
            "history has no rows on or after Champion train_start "
            f"{start.date()}"
        )
    return aligned
