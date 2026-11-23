"""NAR prospective CatBoost 5-feature projector from reviewed PRIOR outcomes.

No provider I/O, no current-race results, no bets. All history must already
be lawfully acquired and independently reviewed. 2023-24 protected holdout
must not be opened or repurposed without a separate research decision.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import re

import pandas as pd

_FEATURES = (
    "past_starts", "past_win_rate", "past_top3_rate",
    "past_mean_finish", "days_since_last_start",
)
_HISTORY = {
    "horse_name", "birth_ymd", "race_day_jst",
    "result_released_utc", "official_status", "finish_rank",
}
_ENTRIES = {"race_id", "horse_id", "horse_name", "birth_ymd"}
_START = {"FINISHED", "DNF_NO_REFUND"}
_SKIP = {"SCRATCH_NOT_OFFERED", "EXCLUDED_REFUND"}
_BIRTH = re.compile(r"[0-9]{8}\Z")


def nar_future_form_features(
    history: pd.DataFrame, entries: pd.DataFrame, *,
    race_day_jst: str, source_asof_utc: datetime,
) -> pd.DataFrame:
    """Recreate prior-start form without leaking future/same-day results.

    This projects source-specific candidate features, not verified source
    rights, prediction accuracy, market execution or economic EV.
    """
    if (not isinstance(history, pd.DataFrame)
            or not isinstance(entries, pd.DataFrame)
            or not isinstance(source_asof_utc, datetime)
            or source_asof_utc.utcoffset() is None
            or history.columns.duplicated().any()
            or entries.columns.duplicated().any()
            or set(history) != _HISTORY or set(entries) != _ENTRIES
            or not 1 <= len(entries) <= 10_000
            or len(history) > 1_000_000):
        raise ValueError("INVALID_NAR_FORM_INPUT_CONTRACT")
    target = date.fromisoformat(race_day_jst)
    cutoff = source_asof_utc.astimezone(timezone.utc)
    if target.isoformat() != race_day_jst:
        raise ValueError("INVALID_NAR_FORM_RACE_DATE")
    if (entries[list(_ENTRIES)].isna().any().any()
            or entries.duplicated(["race_id", "horse_id"]).any()
            or any(type(x) is not str or not x.strip()
                   for field in _ENTRIES for x in entries[field])
            or any(not _BIRTH.fullmatch(x) for x in entries["birth_ymd"])
            or not all(
                x.startswith("NAR:" + target.strftime("%Y%m%d") + ":")
                for x in entries["race_id"]
            )):
        raise ValueError("INVALID_NAR_FUTURE_ROSTER")
    size = entries.groupby("race_id").size()
    if size.lt(4).any() or size.gt(18).any():
        raise ValueError("INCOMPLETE_NAR_FUTURE_ROSTER")
    if (history[list(_HISTORY - {"finish_rank"})].isna().any().any()
            or not all(isinstance(x, str) and x.strip()
                       for field in _HISTORY - {"finish_rank"}
                       for x in history[field])
            or not all(_BIRTH.fullmatch(x) for x in history["birth_ymd"])):
        raise ValueError("INVALID_NAR_HISTORICAL_IDENTITY")
    if not history.empty:
        hdays = pd.to_datetime(
            history["race_day_jst"], format="%Y-%m-%d", errors="raise",
        ).dt.date
        published = pd.to_datetime(
            history["result_released_utc"], utc=True, errors="raise",
        )
        if (hdays.ge(target).any() or published.gt(cutoff).any()
                or history.duplicated(
                    ["horse_name", "birth_ymd", "race_day_jst"]
                ).any() or
                any(s not in _START | _SKIP
                    for s in history["official_status"])):
            raise ValueError("LATE_OR_DUPLICATE_NAR_HISTORY")
        parsed = history.copy()
        parsed["__day"] = hdays
        parsed["__rank"] = pd.to_numeric(parsed["finish_rank"], errors="coerce")
        if (parsed["__rank"].notna() &
                (parsed["__rank"].lt(1) |
                 parsed["__rank"].gt(18) |
                 parsed["__rank"].mod(1).ne(0))).any():
            raise ValueError("INVALID_NAR_FINISH_RANK")
        if (parsed["official_status"].eq("FINISHED") !=
                parsed["__rank"].notna()).any():
            raise ValueError("NAR_STATUS_RANK_MISMATCH")
    else:
        parsed = history.copy()
        parsed["__day"] = pd.Series(dtype="object")
        parsed["__rank"] = pd.Series(dtype="float64")
    # A scratch or exclusion never contributes a prior start. DNF counts
    # as a start, but not as a numeric finisher (same as training logic).
    prior = {}
    for (name, birth), group in parsed.groupby(
        ["horse_name", "birth_ymd"], sort=False,
    ):
        starts = group.loc[group["official_status"].isin(_START)]
        numeric = starts["__rank"].dropna()
        n = len(starts)
        prior[(name, birth)] = (
            n,
            float(numeric.eq(1).sum()) / n if n else 0.0,
            float(numeric.le(3).sum()) / n if n else 0.0,
            float(numeric.mean()) if not numeric.empty else float("nan"),
            float((target - starts["__day"].max()).days) if n else float("nan"),
        )
    out = entries[["race_id", "horse_id"]].copy()
    for field in _FEATURES:
        out[field] = float("nan")
    for i, entry in entries.iterrows():
        features = prior.get(
            (entry["horse_name"], entry["birth_ymd"]),
            (0, 0.0, 0.0, float("nan"), float("nan")),
        )
        for field, value in zip(_FEATURES, features):
            out.at[i, field] = value
    if (set(out) != {"race_id", "horse_id", *_FEATURES}
            or out[["race_id", "horse_id"]].isna().any().any()
            or not out.index.equals(entries.index)):
        raise ValueError("NAR_FUTURE_FORM_OUTPUT_INCOMPLETE")
    return out[["race_id", "horse_id", *_FEATURES]]
