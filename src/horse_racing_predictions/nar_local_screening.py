"""Offline, explicitly operator-authorized NAR 2017–2022 CatBoost screening.

A private list of EXACTLY 72 individually obtained monthly ZIPs is needed.
The later 2023–24 independent evaluation period is NOT read at all. No web
downloads, JV-Link COM, GitHub upload, file output, note, or betting.
This structural gate is intentionally strict: a month with exceptions cannot
be silently reduced to retrospectively profitable training/validation races.

A permission attestation is human supplied, not a legal grant by software.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .nar_local_monthly_intake import _read_nar_local_csv_texts
from .nar_monthly_coverage_audit import audit_nar_monthly_coverage
from .nar_official_zip_probe import UnsafeNarSource, _ZIP_RE
from .nar_prior_day_features import build_prior_day_features
from .nar_private_catboost_screening import (
    NarCatBoostScreeningMetrics, fit_nar_private_catboost_screening,
)

_REQUIRED_MONTHS = frozenset(
    f"{year}{month:02d}" for year in range(2017, 2023)
    for month in range(1, 13)
)
_MAX_DECODED_CHARS = 150_000_000


@dataclass(frozen=True)
class NarLocalScreeningReport:
    status: str
    months_checked: int
    races_checked: int
    metrics: NarCatBoostScreeningMetrics
    local_data_only: bool = True
    real_economic_return_verified: bool = False
    independent_2023_2024_test_opened: bool = False
    note_publication_authorized: bool = False


def screen_nar_local_2017_2022(
    archives: Sequence[Path], *,
    personal_private_permission_confirmed: bool,
    iterations: int = 40,
) -> NarLocalScreeningReport:
    """Train only after verifying all 72 explicit input months, in memory."""
    if (personal_private_permission_confirmed is not True
            or not isinstance(archives, (list, tuple))
            or len(archives) != 72
            or any(not isinstance(p, Path) or not p.is_absolute()
                   for p in archives)
            or len(set(archives)) != len(archives)):
        raise UnsafeNarSource("NAR_72_EXPLICIT_PERSONAL_SOURCES_REQUIRED")

    # Preflight EVERY archive name before reading any source bytes:
    # no accidental opening of 2023–24 unseen or protected 2025–26.
    source_months: set[str] = set()
    for p in archives:
        match = _ZIP_RE.fullmatch(p.name)
        if match is None or match.group(1) not in _REQUIRED_MONTHS:
            raise UnsafeNarSource("NAR_TRAINING_MONTH_INVALID_OR_SEALED")
        month = match.group(1)
        if month in source_months:
            raise UnsafeNarSource("NAR_DUPLICATE_TRAINING_MONTH")
        source_months.add(month)
    if source_months != _REQUIRED_MONTHS:
        raise UnsafeNarSource("NAR_TRAINING_MONTH_COVERAGE_INCOMPLETE")

    texts: dict[str, dict[str, str]] = {}
    total_chars = 0
    observed_races = 0
    for source in archives:
        month, data = _read_nar_local_csv_texts(
            source, personal_private_permission_confirmed=True,
        )
        if month in texts or month not in _REQUIRED_MONTHS:
            raise UnsafeNarSource("NAR_TRAINING_MONTH_MISMATCH")
        total_chars += sum(len(s) for s in data.values())
        if total_chars > _MAX_DECODED_CHARS:
            raise UnsafeNarSource("NAR_LOCAL_MEMORY_BUDGET_EXCEEDED")
        coverage = audit_nar_monthly_coverage(data, month=month).summary
        if coverage.excluded_races:
            raise UnsafeNarSource("NAR_TRAINING_REQUIRES_FULL_REVIEWED_MONTHS")
        texts[month] = {
            "racelist": data["racelist"],
            "horselist": data["horselist"],
        }
        observed_races += coverage.observed_races

    batch = build_prior_day_features(texts)
    if batch.eligible_races != observed_races:
        raise UnsafeNarSource("NAR_TRAINING_RACE_COUNT_CONFLICT")
    candidate = fit_nar_private_catboost_screening(
        batch, iterations=iterations,
    )
    return NarLocalScreeningReport(
        status="NAR_PRIVATE_2022_SCREEN_ONLY_NO_LIVE_ROI",
        months_checked=len(texts),
        races_checked=observed_races,
        metrics=candidate.metrics,
    )
