"""Private JRA preoff source -> exact trained-model features (no network).

Only separately approved, reviewed history and numbered future entries.
No protected holdout discovery, source authentication, wagering or publishing.
"""
from datetime import date, datetime, timedelta, timezone
import re

import pandas as pd

from .dual_candidate_private_preview import LoadedDualResearchCandidate
from .feature_window import align_history_to_training_start
from .inference import build_future_feature_frame
from .odds_free_chronological_eval import _validate_research_features
from .sunday_ai_research import _market_column, _RESULT

_JST = timezone(timedelta(hours=9))
_COURSES = "SAPPORO|HAKODATE|FUKUSHIMA|NIIGATA|NAKAYAMA|TOKYO|CHUKYO|KYOTO|HANSHIN|KOKURA"


def prepare_jra_future_shadow_features(
    candidate: LoadedDualResearchCandidate, *,
    history: pd.DataFrame, entries: pd.DataFrame,
    race_day_jst: str, source_asof: datetime,
    generated_at: datetime, expected_runner_counts: dict[str, int],
) -> pd.DataFrame:
    """Use the original training feature builder, not a guessed feature CSV.

    Source timing and roster review are caller attestations, not independent
    authentication. Require a complete numbered card per declared course.
    """
    day = date.fromisoformat(race_day_jst)
    if (not isinstance(candidate, LoadedDualResearchCandidate)
            or source_asof.utcoffset() is None
            or generated_at.utcoffset() is None
            or source_asof > generated_at
            or generated_at.astimezone(_JST).date() != day
            or source_asof.astimezone(_JST).date() > day):
        raise ValueError("JRA_FUTURE_SOURCE_CHRONOLOGY_INVALID")
    created = datetime.fromisoformat(candidate.generated_at.replace("Z", "+00:00"))
    if (created.utcoffset() is None or created > generated_at
            or date.fromisoformat(candidate.train_end) > date(2024, 12, 31)):
        raise ValueError("JRA_FUTURE_MODEL_CHRONOLOGY_INVALID")
    _validate_research_features(candidate.features)
    required = {"race_id", "race_date", "horse_name", "post_position"}
    for frame, needed in ((history, required | {"finish_position"}),
                          (entries, required)):
        if (not isinstance(frame, pd.DataFrame) or frame.empty
                or frame.columns.duplicated().any() or not needed.issubset(frame)
                or any(str(c).startswith("_") for c in frame.columns)
                or frame[["race_id", "horse_name"]].isna().any().any()
                or frame["horse_name"].astype(str).str.strip().eq("").any()
                or frame.duplicated(["race_id", "horse_name"]).any()):
            raise ValueError("JRA_FUTURE_SOURCE_STRUCTURE_INVALID")
    if (any(_market_column(c) for c in entries.columns)
            or any(entries[c].notna().any() for c in _RESULT.intersection(entries))
            or set(candidate.features).intersection(entries) - {
                "distance_m", "post_position", "age", "carried_weight",
                "horse_weight", "horse_weight_delta", "racecourse", "surface",
                "weather", "track_condition", "sex", "race_class", "graded_race",
            }):
        raise ValueError("JRA_FUTURE_MARKET_OR_OUTCOME_INPUT_INVALID")
    hist_dates = pd.to_datetime(history["race_date"], errors="raise")
    future_dates = pd.to_datetime(entries["race_date"], errors="raise")
    if (hist_dates.isna().any() or future_dates.isna().any()
            or future_dates.dt.date.ne(day).any()
            or hist_dates.max().date() >= source_asof.astimezone(_JST).date()
            or (day - hist_dates.max().date()).days > 14):
        raise ValueError("JRA_FUTURE_HISTORY_STALE_OR_AFTER_CUTOFF")
    if (type(expected_runner_counts) is not dict
            or len(expected_runner_counts) not in (12, 24, 36)
            or any(type(n) is not int or not 4 <= n <= 18
                   for n in expected_runner_counts.values())
            or entries.groupby("race_id").size().to_dict() != expected_runner_counts):
        raise ValueError("JRA_FUTURE_COMPLETE_ROSTER_REQUIRED")
    pattern = re.compile(r"JRA-" + day.strftime("%Y%m%d")
                         + r"-(" + _COURSES + r")-(0[1-9]|1[0-2])\Z")
    by_course = {}
    for rid in expected_runner_counts:
        match = pattern.fullmatch(rid) if isinstance(rid, str) else None
        if match is None:
            raise ValueError("JRA_FUTURE_RACE_ID_INVALID")
        by_course.setdefault(match[1], set()).add(int(match[2]))
    if any(numbers != set(range(1, 13)) for numbers in by_course.values()):
        raise ValueError("JRA_FUTURE_COMPLETE_COURSE_REQUIRED")
    nums = pd.to_numeric(entries["post_position"], errors="coerce")
    if (nums.isna().any() or nums.lt(1).any() or nums.gt(18).any()
            or nums.mod(1).ne(0).any()
            or pd.DataFrame({"race": entries["race_id"], "num": nums}).duplicated().any()):
        raise ValueError("JRA_FUTURE_OFFICIAL_HORSE_NUMBERS_INVALID")
    clean = entries.copy()
    clean["post_position"] = nums.astype(int)
    nonmarket = history.drop(columns=[c for c in history if _market_column(c)])
    aligned = align_history_to_training_start(nonmarket, train_start=candidate.train_start)
    built = build_future_feature_frame(aligned, clean, candidate.features,
                                       max_history_gap_days=14, allow_stale_history=False)
    original_ids = set(zip(clean["race_id"], clean["horse_name"], clean["post_position"]))
    actual_ids = set(zip(built["race_id"], built["horse_name"], built["post_position"]))
    if len(built) != len(clean) or actual_ids != original_ids:
        raise ValueError("JRA_FUTURE_BUILDER_ROSTER_MISMATCH")
    result = built[["race_id", *candidate.features]].copy()
    result["horse_id"] = built["post_position"].astype(int).astype(str)
    return result[["race_id", "horse_id", *candidate.features]].reset_index(drop=True)
