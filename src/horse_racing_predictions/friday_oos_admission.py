"""Pre-registered JRA Friday OOS admission gate before economic evaluation.

Research-only. No model fitting, file/network access, local-provider calls,
price lookup, bet submission or note publication. The race manifest and
timestamps must be independently verified *outside* this structural check.
Never represent its status as source-rights approval or actual positive EV.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Mapping, Sequence

from .oddsfree_ev_research import (
    FinalRaceSettlement, FrozenOddsFreeForecast, select_top3_and_outsider,
)

_JST = timezone(timedelta(hours=9))
_MIN_OOS_RACES = 500
_MIN_OOS_DAYS = 60
_LOCKED_FROM = date(2023, 1, 1)
_LOCKED_THROUGH = date(2024, 12, 31)
_MODEL_SELECTION_THROUGH = date(2022, 12, 31)
# These are reasons, not arbitrary post-hoc choices of poor-performing races.
_ACCEPTED_EXCLUSIONS = frozenset({
    "four_or_fewer_starters",
    "dead_heat",
    "refund_or_scratch",
    "unverified_pre_friday_roster",
    "missing_official_settlement",
    "unverified_payout_provenance",
})


@dataclass(frozen=True)
class FridayOOSAdmission:
    status: str
    scheduled_races: int
    frozen_forecasts: int
    matched_settlements: int
    documented_exclusions: int
    distinct_racing_dates: int
    excluded_by_reason: tuple[tuple[str, int], ...]
    meets_preregistered_sample_minimums: bool
    forecast_clock_and_fold_structurally_verified: bool
    manifest_independently_verified: bool = False
    training_source_rights_verified: bool = False
    payout_rights_verified: bool = False
    historical_friday_availability_independently_verified: bool = False
    positive_expected_value_demonstrated: bool = False
    publication_authorized: bool = False
    protected_final_holdout_opened: bool = False


def _valid_day(value: str) -> date:
    if type(value) is not str:
        raise ValueError("FRIDAY_OOS_NONCANONICAL_DAY")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("FRIDAY_OOS_NONCANONICAL_DAY") from exc
    if d.isoformat() != value:
        raise ValueError("FRIDAY_OOS_NONCANONICAL_DAY")
    return d


def _jst_clock(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("FRIDAY_OOS_NAIVE_CLOCK")
    return value.astimezone(_JST)


def audit_preregistered_friday_oos(
    *,
    expected_races: Mapping[str, str],
    forecasts: Sequence[FrozenOddsFreeForecast],
    settlements: Sequence[FinalRaceSettlement],
    documented_exclusions: Mapping[str, str],
) -> FridayOOSAdmission:
    """Structural coverage and historical Friday freeze evidence, JRA 2023-24.

    expected_races maps the *complete independently reviewed* JRA race IDs
    to Saturday/Sunday YYYY-MM-DD; this function cannot verify provenance.
    Each listed race must have either frozen forecast AND official settlement
    OR one precisely documented exclusion; otherwise it raises. Missing
    settlements are never silently dropped in order to boost ROI.
    """
    if (not isinstance(expected_races, Mapping)
            or not isinstance(documented_exclusions, Mapping)
            or not isinstance(forecasts, (tuple, list))
            or not isinstance(settlements, (tuple, list))
            or not 1 <= len(expected_races) <= 20000
            or len(forecasts) > len(expected_races)
            or len(settlements) > len(expected_races)):
        raise ValueError("FRIDAY_OOS_BOUNDED_MANIFEST_REQUIRED")
    expected = {}
    for race_id, day_string in expected_races.items():
        if (not isinstance(race_id, str)
                or not race_id.startswith("JRA-")
                or not 4 < len(race_id) <= 80):
            raise ValueError("FRIDAY_OOS_JRA_RACE_ID_REQUIRED")
        day = _valid_day(day_string)
        if not (_LOCKED_FROM <= day <= _LOCKED_THROUGH
                and day.weekday() in (5, 6)):
            raise ValueError("FRIDAY_OOS_OUTSIDE_LOCKED_WEEKEND_FOLD")
        expected[race_id] = day
    if not all(isinstance(x, FrozenOddsFreeForecast) for x in forecasts):
        raise ValueError("FRIDAY_OOS_FROZEN_FORECAST_REQUIRED")
    if not all(isinstance(x, FinalRaceSettlement) for x in settlements):
        raise ValueError("FRIDAY_OOS_OFFICIAL_SETTLEMENT_REQUIRED")
    if not all(isinstance(k, str) and isinstance(v, str)
               for k, v in documented_exclusions.items()):
        raise ValueError("FRIDAY_OOS_INVALID_EXCLUSION")
    if (set(documented_exclusions) - set(expected)
            or set(documented_exclusions.values()) - _ACCEPTED_EXCLUSIONS):
        raise ValueError("FRIDAY_OOS_UNREGISTERED_EXCLUSION")

    picks = {}
    model_ids = set()
    for f in forecasts:
        if f.race_id not in expected:
            raise ValueError("FRIDAY_OOS_UNDECLARED_FORECAST_RACE")
        if f.race_id in picks:
            raise ValueError("FRIDAY_OOS_DUPLICATE_FORECAST")
        if f.race_id in documented_exclusions:
            raise ValueError("FRIDAY_OOS_EXCLUDED_RACE_HAS_FORECAST")
        day = _valid_day(f.race_day)
        if day != expected[f.race_id]:
            raise ValueError("FRIDAY_OOS_RACE_DATE_MISMATCH")
        issued = _jst_clock(f.predicted_at_utc)
        off = _jst_clock(f.post_time_utc)
        if (issued.date() != day - timedelta(days=(day.weekday() - 4))
                or issued.weekday() != 4
                or issued.hour < 12
                or off.date() != day
                or issued >= off):
            raise ValueError("FRIDAY_OOS_GENUINE_FRIDAY_FREEZE_REQUIRED")
        fit = _valid_day(f.model_fit_through_day)
        if fit > _MODEL_SELECTION_THROUGH or fit >= issued.date():
            raise ValueError("FRIDAY_OOS_MODEL_FIT_OUTSIDE_FROZEN_FOLD")
        # Run original odds-free field and score checks, without payouts.
        select_top3_and_outsider(f)
        picks[f.race_id] = f
        model_ids.add(f.model_ref)
    if len(model_ids) != 1 and picks:
        raise ValueError("FRIDAY_OOS_SINGLE_FROZEN_MODEL_REQUIRED")
    final = {}
    for result in settlements:
        if result.race_id not in expected:
            raise ValueError("FRIDAY_OOS_UNDECLARED_SETTLEMENT_RACE")
        if result.race_id in final:
            raise ValueError("FRIDAY_OOS_DUPLICATE_SETTLEMENT")
        if result.race_id in documented_exclusions:
            raise ValueError("FRIDAY_OOS_EXCLUDED_RACE_HAS_SETTLEMENT")
        final[result.race_id] = result
    if (set(picks) != set(final)
            or set(expected) != set(picks) | set(documented_exclusions)):
        raise ValueError("FRIDAY_OOS_MISSING_OR_SELECTIVELY_DROPPED_RACE")
    # Ensure payout data refers to the same complete field, but do not read
    # payout amounts or calculate realized ROI in this admission layer.
    for race_id, f in picks.items():
        if set(f.winner_scores) != set(final[race_id].finishing_positions):
            raise ValueError("FRIDAY_OOS_ROSTER_DIFFERENT_AT_SETTLEMENT")
    by_reason = tuple(sorted(
        (reason, sum(v == reason for v in documented_exclusions.values()))
        for reason in set(documented_exclusions.values())
    ))
    days = len({expected[k] for k in picks})
    sufficient = len(picks) >= _MIN_OOS_RACES and days >= _MIN_OOS_DAYS
    return FridayOOSAdmission(
        status=("STRUCTURAL_SAMPLE_MINIMUMS_MET_EXTERNAL_EVIDENCE_REQUIRED"
                if sufficient else "INSUFFICIENT_LOCKED_OOS_SAMPLE"),
        scheduled_races=len(expected), frozen_forecasts=len(picks),
        matched_settlements=len(final),
        documented_exclusions=len(documented_exclusions),
        distinct_racing_dates=days,
        excluded_by_reason=by_reason,
        meets_preregistered_sample_minimums=sufficient,
        forecast_clock_and_fold_structurally_verified=True,
    )
