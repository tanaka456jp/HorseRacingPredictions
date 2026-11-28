"""NAR prospective CatBoost 5-feature projector from reviewed PRIOR outcomes.

No provider I/O, no current-race results, no bets. All history must already
be lawfully acquired and independently reviewed. 2023-24 protected holdout
must not be opened or repurposed without a separate research decision.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
_START = {"FINISHED", "DNF_NO_REFUND", "DISQUALIFIED_REVIEW"}
_SKIP = {"SCRATCH_NOT_OFFERED", "EXCLUDED_REFUND"}
_BIRTH = re.compile(r"[0-9]{8}\Z")


def _birth_before(value: str, day: date) -> bool:
    try:
        return bool(_BIRTH.fullmatch(value)) and datetime.strptime(
            value, "%Y%m%d"
        ).date() < day
    except (TypeError, ValueError):
        return False


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
            or not entries.index.is_unique
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
            or any(not _birth_before(x, target) for x in entries["birth_ymd"])
            or entries.assign(
                horse_name=entries["horse_name"].str.strip()
            ).duplicated(["horse_name", "birth_ymd"]).any()
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
        history = history.copy()
        history["horse_name"] = history["horse_name"].str.strip()
        hdays = pd.to_datetime(
            history["race_day_jst"], format="%Y-%m-%d", errors="raise",
        ).dt.date
        jst = timezone(timedelta(hours=9))
        for day, birth, value in zip(
                hdays, history["birth_ymd"], history["result_released_utc"]):
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if (pd.isna(day) or not _birth_before(birth, day)
                    or stamp.utcoffset() is None
                    or stamp.astimezone(jst).date() < day):
                raise ValueError("NAR_HISTORICAL_IDENTITY_OR_RELEASE_INVALID")
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
        # A missing rank is legitimate only for non-finishers. Do not
        # silently reinterpret malformed source tokens or Boolean ranks
        # as missing/first place when reconstructing prior form.
        if ((parsed["finish_rank"].notna() & parsed["__rank"].isna()).any()
                or parsed["finish_rank"].map(
                    lambda value: isinstance(value, bool)
                ).any()):
            raise ValueError("INVALID_NAR_FINISH_RANK")
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
    # A scratch or exclusion never contributes a prior start. DNF and
    # disqualification count as starts, not numeric finishers, as in the
    # status-aware training projector.
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
            (entry["horse_name"].strip(), entry["birth_ymd"]),
            (0, 0.0, 0.0, float("nan"), float("nan")),
        )
        for field, value in zip(_FEATURES, features):
            out.at[i, field] = value
    if (set(out) != {"race_id", "horse_id", *_FEATURES}
            or out[["race_id", "horse_id"]].isna().any().any()
            or not out.index.equals(entries.index)):
        raise ValueError("NAR_FUTURE_FORM_OUTPUT_INCOMPLETE")
    return out[["race_id", "horse_id", *_FEATURES]]


def prepare_reviewed_nar_full_form(
    history: pd.DataFrame, entries: pd.DataFrame, *,
    race_day_jst: str, source_asof_utc: datetime,
    expected_runner_counts: dict[str, int],
) -> pd.DataFrame:
    """Require independently reviewed career totals to guard missing history.

    Reviewed counts are from a separate permitted source as of the same
    cutoff, not generated from the supplied history. A mismatch is HOLD.
    Career totals must refer to the same flat-racing scope as the training
    history; this function cannot authenticate the review or rights.
    """
    counts = {"reviewed_starts", "reviewed_wins", "reviewed_top3"}
    if (not isinstance(entries, pd.DataFrame)
            or entries.columns.duplicated().any()
            or set(entries) != _ENTRIES | counts
            or not isinstance(history, pd.DataFrame)
            or history.columns.duplicated().any()
            or set(history) != _HISTORY
            or not isinstance(source_asof_utc, datetime)
            or source_asof_utc.utcoffset() is None
            or type(expected_runner_counts) is not dict
            or not expected_runner_counts
            or entries.groupby("race_id").size().to_dict() != expected_runner_counts):
        raise ValueError("NAR_FULL_FORM_REVIEW_CONTRACT_INVALID")
    # Identity and publication chronology are checked in the shared projector.
    reviewed = entries[list(_ENTRIES)].copy().reset_index(drop=True)
    frame = nar_future_form_features(
        history, reviewed, race_day_jst=race_day_jst,
        source_asof_utc=source_asof_utc,
    )
    totals = entries[list(counts)].apply(pd.to_numeric, errors="raise").reset_index(drop=True)
    if (totals.isna().any().any() or (totals < 0).any().any()
            or totals.mod(1).ne(0).any().any()
            or totals["reviewed_wins"].gt(totals["reviewed_top3"]).any()
            or totals["reviewed_top3"].gt(totals["reviewed_starts"]).any()):
        raise ValueError("NAR_FULL_FORM_REVIEW_COUNTS_INVALID")
    # Match integer totals, including zero-start horses. A missing history
    # row for an experienced horse cannot silently become a debut.
    if (frame["past_starts"].ne(totals["reviewed_starts"]).any()
            or (frame["past_starts"] * frame["past_win_rate"]
                - totals["reviewed_wins"]).abs().gt(1e-8).any()
            or (frame["past_starts"] * frame["past_top3_rate"]
                - totals["reviewed_top3"]).abs().gt(1e-8).any()):
        raise ValueError("NAR_FULL_FORM_HISTORY_COVERAGE_MISMATCH")
    return frame
