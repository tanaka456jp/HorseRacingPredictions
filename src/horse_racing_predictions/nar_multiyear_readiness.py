"""NAR multiyear filename coverage and *training-only* source integrity.

2023–24 is the independent, untouched evaluation period. This function may
see the NAMES of candidate held-out ZIP files but must never open their
contents or read those outcomes into a feature accumulator. By design
unseen_2023_2024_races is always ZERO (unknown, not 0 real races).

Only operator-authorized 2017–2022 files are opened month-by-month for
race/settlement consistency and retrospective prior-date research features.
No provider download, JRA-VAN, remote runner, data export or posting.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .nar_local_monthly_intake import _read_nar_local_csv_texts
from .nar_monthly_coverage_audit import (
    audit_nar_monthly_coverage, select_predeclared_flat_races,
)
from .nar_official_zip_probe import UnsafeNarSource, _ZIP_RE
from .nar_incremental_prior_day import build_prior_day_features_month_by_month

_EXPECTED_MONTHS = frozenset(
    f"{year}{month:02d}"
    for year in range(2017, 2025)
    for month in range(1, 13)
)
_TRAIN_TUNE_MONTHS = frozenset(month for month in _EXPECTED_MONTHS
                              if month < "202301")


@dataclass(frozen=True)
class NarMultiMonthReadiness:
    status: str
    observed_months: int
    required_months: int
    missing_months: int
    source_races: int
    predeclared_out_of_scope_races: int
    reconstructed_target_races: int
    reconstructed_runner_rows: int
    fit_2017_2021_races: int
    tune_2022_races: int
    unseen_2023_2024_races: int
    sealed_2023_2024_months_listed: int
    sealed_2023_2024_zip_bytes_opened: bool = False
    training_approved: bool = False
    official_payout_roi_demonstrated: bool = False
    immutable_pre_event_forecast_verified: bool = False
    final_holdout_opened: bool = False
    note_publication_authorized: bool = False


def check_nar_multiyear_local(
    archives: Sequence[Path], *, personal_private_permission_confirmed: bool,
) -> NarMultiMonthReadiness:
    """Check 96-month catalogue without exposing any heldout race results.

    Returns early-period record counts only. All 2023–24 candidate files
    are treated strictly as opaque names, regardless of their content.
    """
    if (personal_private_permission_confirmed is not True
            or not isinstance(archives, (list, tuple))
            or not 1 <= len(archives) <= 96
            or any(not isinstance(p, Path) or not p.is_absolute() for p in archives)
            or len(set(archives)) != len(archives)):
        raise UnsafeNarSource("NAR_EXPLICIT_APPROVED_MONTHLY_SOURCES_REQUIRED")

    # Validate *all* names before accessing even training-period contents.
    month_paths: dict[str, Path] = {}
    for path in archives:
        match = _ZIP_RE.fullmatch(path.name)
        if match is None or match.group(1) not in _EXPECTED_MONTHS:
            raise UnsafeNarSource("NAR_DUPLICATE_OR_OUTSIDE_RESEARCH_MONTH")
        month = match.group(1)
        if month in month_paths:
            raise UnsafeNarSource("NAR_DUPLICATE_OR_OUTSIDE_RESEARCH_MONTH")
        month_paths[month] = path

    total = {"source": 0, "flat": 0, "banei": 0}

    def training_months():
        for month in sorted(set(month_paths) & _TRAIN_TUNE_MONTHS):
            actual, texts = _read_nar_local_csv_texts(
                month_paths[month], personal_private_permission_confirmed=True,
            )
            if actual != month:
                raise UnsafeNarSource("NAR_TRAINING_MONTH_MISMATCH")
            coverage = audit_nar_monthly_coverage(texts, month=month).summary
            if not coverage.complete_month_for_research:
                raise UnsafeNarSource("NAR_MULTIMONTH_HAS_EXCLUDED_RACES_ROI_BLOCKED")
            clean = select_predeclared_flat_races(texts, month=month)
            total["source"] += coverage.observed_races
            total["flat"] += coverage.structurally_accepted_races
            total["banei"] += coverage.predeclared_out_of_scope_races
            yield month, {
                "racelist": clean["racelist"],
                "horselist": clean["horselist"],
            }

    fit, tune, runners = 0, 0, 0
    if set(month_paths) & _TRAIN_TUNE_MONTHS:
        batch = build_prior_day_features_month_by_month(training_months())
        if batch.eligible_races != total["flat"]:
            raise UnsafeNarSource("NAR_MULTIMONTH_RACE_COUNT_CONFLICT")
        distinct: dict[int, set[tuple[str, str, int]]] = {}
        for row in batch.return_data:
            year = int(row.race_day[:4])
            distinct.setdefault(year, set()).add(row.race_key)
        fit = sum(len(items) for yr, items in distinct.items() if yr <= 2021)
        tune = sum(len(items) for yr, items in distinct.items() if yr == 2022)
        runners = batch.target_runner_rows
    else:
        batch = None

    missing = len(_EXPECTED_MONTHS - set(month_paths))
    sealed_listed = len(set(month_paths) - _TRAIN_TUNE_MONTHS)
    return NarMultiMonthReadiness(
        status=(
            "NAR_ALL_96_MONTH_NAMES_PRESENT_2023_2024_UNOPENED"
            if missing == 0
            else "NAR_PARTIAL_MONTH_COVERAGE_SEALED_MONTHS_UNOPENED"
        ),
        observed_months=len(month_paths),
        required_months=len(_EXPECTED_MONTHS),
        missing_months=missing,
        source_races=total["source"],
        predeclared_out_of_scope_races=total["banei"],
        reconstructed_target_races=total["flat"],
        reconstructed_runner_rows=runners,
        fit_2017_2021_races=fit,
        tune_2022_races=tune,
        unseen_2023_2024_races=0,
        sealed_2023_2024_months_listed=sealed_listed,
    )
