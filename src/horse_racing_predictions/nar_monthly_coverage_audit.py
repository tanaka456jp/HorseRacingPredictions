"""Privacy-safe complete-month NAR exclusion ledger; no source data export.

A finalized monthly NAR ZIP can contain ordinary races, ties, scratches,
short fields and unavailable settlement. Do NOT filter that month down to
winning/clean bets and report its ROI. This module accounts for EVERY race
key found in ANY of the three published CSV members, with a static failure
reason and a hard fail-closed ROI gate when any race is ineligible.

Only in-memory, operator-permitted text; no network, no ZIPs, no file writes,
no model training or event-time information. The underlying strict
per-race normalizer is reused rather than reimplementing payout rules.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Mapping
import csv

from .nar_official_zip_probe import UnsafeNarSource
from .nar_published_result_normalizer import (
    _EXPECTED_WIDTH, _parse, RaceKey, normalize_nar_published_results,
)


@dataclass(frozen=True)
class NarRaceExclusion:
    key: RaceKey = field(repr=False)
    reason_code: str


@dataclass(frozen=True)
class NarMonthlyCoverage:
    status: str
    month: str
    observed_races: int
    structurally_accepted_races: int
    excluded_races: int
    exclusion_reasons: tuple[tuple[str, int], ...]
    complete_month_for_research: bool
    actual_source_rights_verified: bool = False
    pre_event_snapshot_verified: bool = False
    approved_for_model_training: bool = False
    valid_economic_roi_sample: bool = False
    positive_ev_demonstrated: bool = False
    publication_authorized: bool = False


@dataclass(frozen=True)
class NarMonthlyCoverageDetail:
    summary: NarMonthlyCoverage
    exclusions: tuple[NarRaceExclusion, ...] = field(repr=False)


def _as_csv(rows: list[list[str]]) -> str:
    buf = StringIO(newline="")
    csv.writer(buf).writerows(rows)
    return buf.getvalue()


def audit_nar_monthly_coverage(
    csv_texts: Mapping[str, str], *, month: str,
) -> NarMonthlyCoverageDetail:
    """A whole-month, descriptive-only denominator and exclusion ledger.

    Width, dates and CSV syntax are still global fail-closed conditions.
    A race-scoped settlement anomaly is counted and disclosed by reason;
    NO subset is returned for model fitting or ROI.
    """
    if (not isinstance(csv_texts, Mapping)
            or set(csv_texts) != set(_EXPECTED_WIDTH)):
        raise UnsafeNarSource("NAR_EXPLICIT_THREE_CSVS_AND_MONTH_REQUIRED")

    parsed = {kind: _parse(csv_texts[kind], kind, month)
              for kind in _EXPECTED_WIDTH}
    groups: dict[str, dict[RaceKey, list[list[str]]]] = {}
    for kind, entries in parsed.items():
        grouped: dict[RaceKey, list[list[str]]] = defaultdict(list)
        for key, row in entries:
            grouped[key].append(row)
        groups[kind] = grouped

    all_keys = sorted(set().union(*(set(group) for group in groups.values())))
    if not all_keys:
        raise UnsafeNarSource("NAR_MONTH_HAS_NO_RACES")
    reasons: Counter[str] = Counter()
    errors: list[NarRaceExclusion] = []
    accepted = 0

    for key in all_keys:
        if any(key not in groups[kind] for kind in _EXPECTED_WIDTH):
            code = "NAR_RACE_COVERAGE_MISMATCH"
        else:
            subset = {
                kind: _as_csv(groups[kind][key]) for kind in _EXPECTED_WIDTH
            }
            try:
                normalize_nar_published_results(subset, month=month)
            except UnsafeNarSource as exc:
                # Our normalizer raises static error identifiers only.
                # Never persist a raw CSV cell, name, or private race key.
                code = str(exc)
            else:
                accepted += 1
                continue
        reasons[code] += 1
        errors.append(NarRaceExclusion(key=key, reason_code=code))

    rejected = len(errors)
    complete = rejected == 0
    report = NarMonthlyCoverage(
        status=(
            "NAR_MONTH_STRUCTURE_COMPLETE_PRE_EVENT_UNVERIFIED"
            if complete
            else "NAR_MONTH_HAS_EXCLUSIONS_RESEARCH_ROI_BLOCKED"
        ),
        month=month,
        observed_races=len(all_keys),
        structurally_accepted_races=accepted,
        excluded_races=rejected,
        exclusion_reasons=tuple(sorted(reasons.items())),
        complete_month_for_research=complete,
    )
    assert report.observed_races == report.structurally_accepted_races + report.excluded_races
    assert sum(n for _, n in report.exclusion_reasons) == report.excluded_races
    return NarMonthlyCoverageDetail(
        summary=report, exclusions=tuple(errors),
    )
