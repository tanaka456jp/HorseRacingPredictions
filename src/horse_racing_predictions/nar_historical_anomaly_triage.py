"""Pure aggregate triage of licensed NAR 2017-2022 training source anomalies.

Uses ONLY the already-created, post-event 72-month report. No opening
private ZIPs, race/horse IDs, payback values, odds, held-out outcomes,
network requests or profitable-subset data release. Fail closed if any
month is missing/corrupt or if strict/status-aware denominators disagree.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re

from .nar_official_zip_probe import UnsafeNarSource
from .nar_training_preflight import NarPreflightReport

_STATIC_REASON = re.compile(r"NAR_[A-Z0-9_]{1,96}\Z")
_EXPECTED = tuple(f"{year}{month:02d}" for year in range(2017, 2023)
                  for month in range(1, 13))
_CATEGORY_BY_REASON = {
    "NAR_STATUS_AWARE_PLACE_PAYOUT_MISMATCH": "PLACE_TICKET_RULE_REVIEW",
    "NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS": "DQ_SETTLEMENT_PRIMARY_SOURCE",
    "NAR_WIN_PAYOUT_BOTH_MISSING_AND_UNEXPECTED": "WIN_PAYOUT_CONFLICT",
    "NAR_WIN_PAYOUT_MISSING_RANK_ONE": "WIN_PAYOUT_CONFLICT",
    "NAR_WIN_PAYOUT_TO_NON_RANK_ONE": "WIN_PAYOUT_CONFLICT",
    "NAR_OFFICIAL_MULTIROW_PAYOUT_CONFLICT": "MULTIROW_PAYOUT_REVIEW",
    "NAR_IDENTICAL_DUPLICATE_PAYOUT_ROW": "MULTIROW_PAYOUT_REVIEW",
    "NAR_EXCESSIVE_OFFICIAL_PAYOUT_ROWS": "MULTIROW_PAYOUT_REVIEW",
    "NAR_STATUS_AWARE_COVERAGE_MISMATCH": "MISSING_RACE_SOURCE_ROWS",
    "NAR_BLANK_WITHOUT_OFFICIAL_STATUS": "FINAL_STATUS_PROVENANCE",
    "NAR_CONFLICTING_RANK_AND_EXCEPTION": "FINAL_STATUS_PROVENANCE",
    "NAR_STATUS_AWARE_RANKS_INCOMPLETE": "FINAL_RANK_PROVENANCE",
    "NAR_FINISH_RANK_INVALID": "FINAL_RANK_PROVENANCE",
}


@dataclass(frozen=True)
class NarAnomalyByYear:
    year: int
    source_months: int
    total_flat_races: int
    strict_unresolved_flat: int
    status_aware_unresolved_flat: int
    status_aware_reconciled_flat: int
    status_complete_months: int


@dataclass(frozen=True)
class NarHistoricalAnomalyTriage:
    status: str
    months_verified: int
    flat_races: int
    strict_unresolved_flat: int
    status_aware_unresolved_flat: int
    newly_interpreted_flat: int
    by_year: tuple[NarAnomalyByYear, ...]
    by_reason: tuple[tuple[str, int], ...]
    by_category: tuple[tuple[str, int], ...]
    # Anomaly explanations are POST-EVENT diagnostics, never labels
    # authorized for real ROI or permissive subset selection.
    source_records_exported: bool = False
    individual_race_identifiers_exported: bool = False
    historical_protected_oos_opened: bool = False
    training_rows_released: int = 0
    actual_cost_adjusted_roi_evaluated: bool = False
    positive_expected_value_demonstrated: bool = False


def triage_historical_nar_anomalies(
    report: NarPreflightReport,
) -> NarHistoricalAnomalyTriage:
    if (not isinstance(report, NarPreflightReport)
            or report.months_present != 72
            or report.months_missing != 0
            or report.missing_month_ids
            or len(report.diagnostic) != 72
            or tuple(item.month for item in report.diagnostic) != _EXPECTED
            or report.model_training_performed
            or report.payouts_or_roi_evaluated
            or report.protected_holdout_opened
            or report.data_sent_to_network):
        raise UnsafeNarSource("NAR_TRIAGE_COMPLETE_PRIVATE_TRAINING_MONTHS_REQUIRED")

    reasons: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    years: list[NarAnomalyByYear] = []
    strict_total = status_total = validated = total_flat = complete = 0

    for year in range(2017, 2023):
        entries = report.diagnostic[(year - 2017) * 12:(year - 2016) * 12]
        s_strict = s_status = s_valid = s_flat = s_complete = 0
        for item in entries:
            if (item.status == "MONTH_SOURCE_REJECTED"
                    or item.race_count <= 0 or item.accepted_flat_races < 0
                    or item.out_of_scope_banei_races < 0
                    or item.unresolved_flat_races < 0
                    or item.status_aware_validated_flat_races < 0
                    or item.status_aware_unresolved_flat_races < 0):
                raise UnsafeNarSource("NAR_TRIAGE_REJECTED_MONTH_OR_INVALID_COUNTS")
            flat = item.race_count - item.out_of_scope_banei_races
            if (flat <= 0
                    or flat != item.accepted_flat_races + item.unresolved_flat_races
                    or flat != (
                        item.status_aware_validated_flat_races
                        + item.status_aware_unresolved_flat_races)
                    or item.status_aware_validated_flat_races <
                       item.accepted_flat_races
                    or sum(n for _, n in item.status_aware_reasons)
                       != item.status_aware_unresolved_flat_races):
                raise UnsafeNarSource("NAR_TRIAGE_RACE_DENOMINATOR_CONFLICT")
            for reason, n in item.status_aware_reasons:
                if (type(reason) is not str
                        or not _STATIC_REASON.fullmatch(reason)
                        or type(n) is not int or n < 1):
                    raise UnsafeNarSource("NAR_TRIAGE_UNSAFE_REASON_CODE")
                category = _CATEGORY_BY_REASON.get(reason, "UNKNOWN_REQUIRES_REVIEW")
                reasons[reason] += n
                categories[category] += n
            s_flat += flat
            s_strict += item.unresolved_flat_races
            s_status += item.status_aware_unresolved_flat_races
            s_valid += item.status_aware_validated_flat_races
            s_complete += int(item.status_aware_unresolved_flat_races == 0)
        years.append(NarAnomalyByYear(
            year=year, source_months=12, total_flat_races=s_flat,
            strict_unresolved_flat=s_strict,
            status_aware_unresolved_flat=s_status,
            status_aware_reconciled_flat=s_valid,
            status_complete_months=s_complete,
        ))
        strict_total += s_strict
        status_total += s_status
        validated += s_valid
        total_flat += s_flat
        complete += s_complete

    if (strict_total != report.unresolved_flat_races
            or status_total != report.status_aware_unresolved_flat_races
            or validated != report.status_aware_validated_flat_races
            or validated + status_total != total_flat
            or complete != report.months_status_aware_complete
            or sum(reasons.values()) != status_total
            or sum(categories.values()) != status_total
            or strict_total < status_total):
        raise UnsafeNarSource("NAR_TRIAGE_ALL_PERIOD_TOTALS_CONFLICT")

    return NarHistoricalAnomalyTriage(
        status=("NAR_ALL_72_MONTHS_AGGREGATE_TRIAGE_NO_RELEASE"
                if status_total else
                "NAR_ALL_72_MONTHS_STATUS_INTERPRETED_NO_PREOFF_PROOF"),
        months_verified=72,
        flat_races=total_flat,
        strict_unresolved_flat=strict_total,
        status_aware_unresolved_flat=status_total,
        newly_interpreted_flat=strict_total - status_total,
        by_year=tuple(years),
        by_reason=tuple(sorted(reasons.items(), key=lambda x: (-x[1], x[0]))),
        by_category=tuple(sorted(categories.items(), key=lambda x: (-x[1], x[0]))),
    )
