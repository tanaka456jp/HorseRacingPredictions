"""Local operator-supplied multiyear NAR readiness (no download or files written).

Strictly reads explicitly nominated official-format local ZIPs already
acquired with the required permission. As-of-form construction reads only
prior race days. All partial coverage is disclosed; synthetic verification
is NOT a real-world ROI or a real, timestamped pre-race prediction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence

from .nar_local_monthly_intake import _read_nar_local_csv_texts
from .nar_monthly_coverage_audit import audit_nar_monthly_coverage
from .nar_official_zip_probe import UnsafeNarSource
from .nar_prior_day_features import build_prior_day_features

_START = date(2017, 1, 1)
_END = date(2024, 12, 31)
_EXPECTED_MONTHS = frozenset(
    f"{year}{month:02d}"
    for year in range(2017, 2025)
    for month in range(1, 13)
)


@dataclass(frozen=True)
class NarMultiMonthReadiness:
    status: str
    observed_months: int
    required_months: int
    missing_months: int
    source_races: int
    reconstructed_target_races: int
    reconstructed_runner_rows: int
    fit_2017_2021_races: int
    tune_2022_races: int
    unseen_2023_2024_races: int
    training_approved: bool = False
    official_payout_roi_demonstrated: bool = False
    immutable_pre_event_forecast_verified: bool = False
    final_holdout_opened: bool = False
    note_publication_authorized: bool = False


def check_nar_multiyear_local(
    archives: Sequence[Path], *, personal_private_permission_confirmed: bool,
) -> NarMultiMonthReadiness:
    """Audit complete named local monthly source list, fail closed.

    A file path is never printed, output, or sent to a network endpoint.
    This does NOT accept directories, generic wildcards, URLs or NAR odds ZIPs.
    """
    if (personal_private_permission_confirmed is not True
            or not isinstance(archives, (list, tuple))
            or not 1 <= len(archives) <= 96
            or any(not isinstance(p, Path) or not p.is_absolute() for p in archives)
            or len(set(archives)) != len(archives)):
        raise UnsafeNarSource("NAR_EXPLICIT_APPROVED_MONTHLY_SOURCES_REQUIRED")

    months: dict[str, dict[str, str]] = {}
    total_races = 0
    for source in archives:
        month, texts = _read_nar_local_csv_texts(
            source, personal_private_permission_confirmed=True,
        )
        if month not in _EXPECTED_MONTHS or month in months:
            raise UnsafeNarSource("NAR_DUPLICATE_OR_OUTSIDE_RESEARCH_MONTH")
        coverage = audit_nar_monthly_coverage(texts, month=month).summary
        if coverage.excluded_races:
            # Do not select only the accepted races to improve backtest.
            raise UnsafeNarSource("NAR_MULTIMONTH_HAS_EXCLUDED_RACES_ROI_BLOCKED")
        months[month] = {
            "racelist": texts["racelist"],
            "horselist": texts["horselist"],
        }
        total_races += coverage.observed_races

    batch = build_prior_day_features(months)
    if batch.eligible_races != total_races:
        raise UnsafeNarSource("NAR_MULTIMONTH_RACE_COUNT_CONFLICT")

    fit, tune, unseen = 0, 0, 0
    # Count distinct races rather than horse rows to prevent a field-size bias.
    race_by_year: dict[int, set[tuple[str, str, int]]] = {}
    for target in batch.return_data:
        year = int(target.race_day[:4])
        race_by_year.setdefault(year, set()).add(target.race_key)
    for year, race_keys in race_by_year.items():
        if year <= 2021:
            fit += len(race_keys)
        elif year == 2022:
            tune += len(race_keys)
        else:
            unseen += len(race_keys)
    missing = len(_EXPECTED_MONTHS - set(months))
    return NarMultiMonthReadiness(
        status=(
            "NAR_HISTORICAL_FOLDS_COMPLETE_NO_PREOFF_OR_REAL_EV_PROOF"
            if missing == 0
            else "NAR_PARTIAL_MONTH_COVERAGE_NO_REAL_ROI_INFERENCE"
        ),
        observed_months=len(months),
        required_months=len(_EXPECTED_MONTHS),
        missing_months=missing,
        source_races=total_races,
        reconstructed_target_races=batch.eligible_races,
        reconstructed_runner_rows=batch.target_runner_rows,
        fit_2017_2021_races=fit,
        tune_2022_races=tune,
        unseen_2023_2024_races=unseen,
    )
