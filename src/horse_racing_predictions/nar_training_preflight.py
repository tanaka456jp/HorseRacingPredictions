"""Offline NAR 2017–2022 month-by-month diagnostic, independent of fitting.

This is a *preflight*, not a model training gate or any ROI estimator.
The user chooses the local approved NAR folder explicitly. Missing ZIPs,
per-month schema/CRC/size errors, and published settlement/field anomalies
are aggregated without outputting a horse, race, raw CSV, source file path,
score, betting return, or repository artifact.

Only 2017–2022 contents can be opened. 2023–2024 and protected 2025+
never enter this path, even as ZIP contents. No network, providers, JRA-VAN,
cloud CI, bookmaker, note or model training.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .nar_private_manifest_inventory import (
    inventory_private_nar_training_directory,
)
from .nar_local_monthly_intake import _read_nar_local_csv_texts
from .nar_monthly_coverage_audit import audit_nar_monthly_coverage
from .nar_official_exception_audit import audit_nar_official_exceptions
from .nar_official_zip_probe import UnsafeNarSource


@dataclass(frozen=True)
class NarMonthDiagnostic:
    month: str
    status: str
    race_count: int
    accepted_flat_races: int
    out_of_scope_banei_races: int
    unresolved_flat_races: int
    static_reasons: tuple[tuple[str, int], ...]
    # Independently audited post-event official status/settlement, not
    # released as pre-off training rows or an ROI denominator.
    status_aware_validated_flat_races: int = 0
    status_aware_unresolved_flat_races: int = 0
    status_aware_reasons: tuple[tuple[str, int], ...] = ()
    ambiguous_finish_pattern_counts: tuple[tuple[str, int], ...] = ()
    unrecognized_marker_profile_counts: tuple[tuple[str, int], ...] = ()
    unknown_marker_rank_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_win_payout_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_monthly_distinct_sum: int = 0
    unknown_marker_max_monthly_single_value_frequency: int = 0
    unknown_marker_race_pattern_counts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class NarPreflightReport:
    status: str
    months_present: int
    months_missing: int
    missing_month_ids: tuple[str, ...]
    months_structurally_accepted: int
    months_with_unresolved_errors: int
    observed_races: int
    accepted_flat_races: int
    out_of_scope_banei_races: int
    unresolved_flat_races: int
    diagnostic: tuple[NarMonthDiagnostic, ...]
    # Parallel official-status interpretation never relaxes the separate
    # rank-only training gate or the missing-month requirement.
    status_aware_validated_flat_races: int = 0
    status_aware_unresolved_flat_races: int = 0
    months_status_aware_complete: int = 0
    ambiguous_finish_pattern_counts: tuple[tuple[str, int], ...] = ()
    unrecognized_marker_profile_counts: tuple[tuple[str, int], ...] = ()
    unknown_marker_rank_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_win_payout_evidence: tuple[tuple[str, int], ...] = ()
    unknown_marker_monthly_distinct_sum: int = 0
    unknown_marker_max_monthly_single_value_frequency: int = 0
    unknown_marker_race_pattern_counts: tuple[tuple[str, int], ...] = ()
    user_permission_attested: bool = True
    all_months_study_eligible: bool = False
    actual_rights_independently_verified: bool = False
    model_training_performed: bool = False
    payouts_or_roi_evaluated: bool = False
    protected_holdout_opened: bool = False
    data_sent_to_network: bool = False


def diagnose_nar_training_folder(
    folder: Path, *, personal_private_permission_confirmed: bool,
) -> NarPreflightReport:
    """Evaluate all present approved training months, never stop at one bad ZIP.

    Directory inventory is metadata-only and fail-closed for symlinks, an
    unexpected ZIP (including 2023+), or an old JRA-VAN archive. Individual
    corrupt NAR 2017–2022 files are counted rather than hiding other months.
    """
    inventory = inventory_private_nar_training_directory(
        folder, personal_private_permission_confirmed=personal_private_permission_confirmed,
    )
    detail: list[NarMonthDiagnostic] = []
    observed = accepted = banei = unresolved = complete = 0
    status_accepted = status_unresolved = status_complete = 0
    ambiguous_patterns: Counter[str] = Counter()
    unrecognized_profiles: Counter[str] = Counter()
    unknown_rank_evidence: Counter[str] = Counter()
    unknown_win_evidence: Counter[str] = Counter()
    unknown_race_patterns: Counter[str] = Counter()
    unknown_distinct_monthly_sum = 0
    unknown_max_monthly_frequency = 0
    for source in inventory.absolute_source_paths:
        month = source.name[:6]
        try:
            checked_month, texts = _read_nar_local_csv_texts(
                source, personal_private_permission_confirmed=True,
            )
            if checked_month != month:
                raise UnsafeNarSource("NAR_PREFLIGHT_MONTH_MISMATCH")
            coverage = audit_nar_monthly_coverage(texts, month=month).summary
            # Read the *same* already-decoded private bytes only; never
            # fetch a new source, open a held-out ZIP or expose horse IDs.
            outcome = audit_nar_official_exceptions(texts, month=month).audit
            if (outcome.source_races != coverage.observed_races
                    or outcome.predeclared_banei_races !=
                       coverage.predeclared_out_of_scope_races
                    or outcome.in_scope_flat_races != (
                        coverage.observed_races
                        - coverage.predeclared_out_of_scope_races
                    )
                    or outcome.status_validated_flat_races
                       + outcome.unresolved_flat_races
                       != outcome.in_scope_flat_races
                    or outcome.status_validated_flat_races <
                       coverage.structurally_accepted_races):
                raise UnsafeNarSource("NAR_PREFLIGHT_PARALLEL_AUDIT_DISAGREEMENT")
            if (sum(n for _, n in outcome.ambiguous_finish_pattern_counts)
                    != dict(outcome.unresolved_reason_counts).get(
                        "NAR_BLANK_WITHOUT_OFFICIAL_STATUS", 0
                    )):
                raise UnsafeNarSource("NAR_PREFLIGHT_AMBIGUOUS_SHAPE_COUNT_CONFLICT")
            ambiguous_patterns.update(dict(outcome.ambiguous_finish_pattern_counts))
            unrecognized_profiles.update(dict(outcome.unrecognized_marker_profile_counts))
            n_nonempty = dict(outcome.ambiguous_finish_pattern_counts).get(
                "UNRECOGNIZED_NONEMPTY_STATUS_MARKER", 0
            )
            if (sum(n for _, n in outcome.unknown_marker_rank_evidence) != n_nonempty
                    or sum(n for _, n in outcome.unknown_marker_win_payout_evidence)
                       != n_nonempty):
                raise UnsafeNarSource("NAR_PREFLIGHT_UNKNOWN_MARKER_EVIDENCE_CONFLICT")
            unknown_rank_evidence.update(dict(outcome.unknown_marker_rank_evidence))
            unknown_win_evidence.update(dict(outcome.unknown_marker_win_payout_evidence))
            p = dict(outcome.unknown_marker_race_pattern_counts)
            if (p.get("SAME_UNKNOWN_TEXT_ALL_HORSES", 0)
                    + p.get("MIXED_UNKNOWN_TEXT_OR_PARTIAL_HORSES", 0)
                    != n_nonempty
                    or p.get("OFFICIAL_LIKE_CANCEL_SPELLING_UNVERIFIED", 0)
                    + p.get("NOT_OFFICIAL_LIKE_CANCEL_SPELLING", 0)
                    != n_nonempty):
                raise UnsafeNarSource("NAR_PREFLIGHT_UNKNOWN_RACE_PATTERN_CONFLICT")
            unknown_race_patterns.update(p)
            unknown_distinct_monthly_sum += (
                outcome.unknown_marker_distinct_text_values_in_month
            )
            unknown_max_monthly_frequency = max(
                unknown_max_monthly_frequency,
                outcome.unknown_marker_largest_single_value_frequency_in_month,
            )
            reasons = coverage.exclusion_reasons
            is_valid = coverage.complete_month_for_research
            observed += coverage.observed_races
            accepted += coverage.structurally_accepted_races
            banei += coverage.predeclared_out_of_scope_races
            unresolved += coverage.unresolved_in_scope_races
            status_accepted += outcome.status_validated_flat_races
            status_unresolved += outcome.unresolved_flat_races
            status_complete += int(outcome.complete_flat_outcome_interpretation)
            if is_valid:
                complete += 1
            detail.append(NarMonthDiagnostic(
                month=month,
                status="FLAT_RACES_STRUCTURALLY_VALID" if is_valid
                       else "IN_SCOPE_ANOMALY_REQUIRES_REVIEW",
                race_count=coverage.observed_races,
                accepted_flat_races=coverage.structurally_accepted_races,
                out_of_scope_banei_races=coverage.predeclared_out_of_scope_races,
                unresolved_flat_races=coverage.unresolved_in_scope_races,
                static_reasons=reasons,
                status_aware_validated_flat_races=outcome.status_validated_flat_races,
                status_aware_unresolved_flat_races=outcome.unresolved_flat_races,
                status_aware_reasons=outcome.unresolved_reason_counts,
                ambiguous_finish_pattern_counts=(
                    outcome.ambiguous_finish_pattern_counts
                ),
                unrecognized_marker_profile_counts=(
                    outcome.unrecognized_marker_profile_counts
                ),
                unknown_marker_rank_evidence=outcome.unknown_marker_rank_evidence,
                unknown_marker_win_payout_evidence=(
                    outcome.unknown_marker_win_payout_evidence
                ),
                unknown_marker_race_pattern_counts=(
                    outcome.unknown_marker_race_pattern_counts
                ),
                unknown_marker_monthly_distinct_sum=(
                    outcome.unknown_marker_distinct_text_values_in_month
                ),
                unknown_marker_max_monthly_single_value_frequency=(
                    outcome.unknown_marker_largest_single_value_frequency_in_month
                ),
            ))
        except (UnsafeNarSource, OSError, RuntimeError, UnicodeError) as exc:
            # Never print Python tracebacks and never reflect arbitrary
            # source content through error messages. Internal exceptions
            # are static codes by contract; unknown errors get one generic
            # public identifier instead of leaking a file/CSV path.
            code = str(exc) if isinstance(exc, UnsafeNarSource) else "NAR_LOCAL_FILE_READ_FAILED"
            if not code.startswith("NAR_") or len(code) > 100:
                code = "NAR_PRIVATE_SOURCE_REJECTED"
            detail.append(NarMonthDiagnostic(
                month=month,
                status="MONTH_SOURCE_REJECTED",
                race_count=0,
                accepted_flat_races=0,
                out_of_scope_banei_races=0,
                unresolved_flat_races=0,
                static_reasons=((code, 1),),
            ))
    all_good = not inventory.missing_months and complete == 72
    return NarPreflightReport(
        status=("NAR_72_MONTHS_STRUCTURALLY_READY_FOR_SEPARATE_PRIVATE_REVIEW"
                if all_good else "NAR_TRAINING_SOURCES_INCOMPLETE_OR_ANOMALOUS"),
        months_present=inventory.observed_months,
        months_missing=len(inventory.missing_months),
        missing_month_ids=inventory.missing_months,
        months_structurally_accepted=complete,
        months_with_unresolved_errors=len(detail)-complete,
        observed_races=observed,
        accepted_flat_races=accepted,
        out_of_scope_banei_races=banei,
        unresolved_flat_races=unresolved,
        diagnostic=tuple(detail),
        status_aware_validated_flat_races=status_accepted,
        status_aware_unresolved_flat_races=status_unresolved,
        months_status_aware_complete=status_complete,
        ambiguous_finish_pattern_counts=tuple(sorted(
            ambiguous_patterns.items()
        )),
        unrecognized_marker_profile_counts=tuple(sorted(
            unrecognized_profiles.items()
        )),
        unknown_marker_rank_evidence=tuple(sorted(unknown_rank_evidence.items())),
        unknown_marker_win_payout_evidence=tuple(sorted(
            unknown_win_evidence.items()
        )),
        unknown_marker_race_pattern_counts=tuple(sorted(
            unknown_race_patterns.items()
        )),
        unknown_marker_monthly_distinct_sum=unknown_distinct_monthly_sum,
        unknown_marker_max_monthly_single_value_frequency=(
            unknown_max_monthly_frequency
        ),
        all_months_study_eligible=False,  # source rights/timing never certified
    )
