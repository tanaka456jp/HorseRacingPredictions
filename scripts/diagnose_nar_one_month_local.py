"""Privacy-safe diagnostic for one explicitly selected, permitted NAR month.

Unlike the production screening CLI, this displays the *static error code*
and stage for operator remediation. Never output source paths, horse or race
identities, raw CSV, or full exception messages / tracebacks. No network,
training, publishing, upload, download, or writing files.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from horse_racing_predictions.nar_official_zip_probe import (
    UnsafeNarSource, _ZIP_RE, inspect_nar_monthly_zip_structure,
)
from horse_racing_predictions.nar_local_monthly_intake import (
    _read_nar_local_csv_texts,
)
from horse_racing_predictions.nar_monthly_coverage_audit import (
    audit_nar_monthly_coverage,
)
from horse_racing_predictions.nar_official_exception_audit import (
    audit_nar_official_exceptions,
)
from horse_racing_predictions.nar_status_aware_training_labels import (
    derive_nar_status_aware_outcome_labels,
)

_STATIC = re.compile(r"NAR_[A-Z0-9_]{1,90}\Z")


def diagnose_nar_month(
    path: Path, *, expected_month: str, personal_private_permission_confirmed: bool,
) -> dict:
    if personal_private_permission_confirmed is not True:
        raise UnsafeNarSource("NAR_PERSONAL_RESEARCH_PERMISSION_REQUIRED")
    if (not isinstance(expected_month, str)
            or expected_month not in {
                f"{year}{month:02d}"
                for year in range(2017, 2023) for month in range(1, 13)
            }):
        raise UnsafeNarSource("NAR_DIAGNOSTIC_TRAINING_MONTH_ONLY")
    if not isinstance(path, Path) or not path.is_absolute():
        raise UnsafeNarSource("NAR_ABSOLUTE_LOCAL_ZIP_REQUIRED")
    match = _ZIP_RE.fullmatch(path.name)
    if match is None or match.group(1) != expected_month:
        raise UnsafeNarSource("NAR_DIAGNOSTIC_UNEXPECTED_MONTH_OR_ZIP_NAME")

    def safe_failure(stage: str, exc: Exception) -> dict:
        code = str(exc) if isinstance(exc, UnsafeNarSource) else ""
        if not _STATIC.fullmatch(code):
            code = "NAR_PRIVATE_DIAGNOSTIC_READ_FAILED"
        return {
            "status": "NAR_PRIVATE_MONTH_DIAGNOSTIC_BLOCKED",
            "stage": stage,
            "reasonCode": code,
            "month": expected_month,
            "sourceBytesUploaded": False,
            "modelTrainingExecuted": False,
            "positiveEvDemonstrated": False,
            "protectedHoldoutOpened": False,
        }

    try:
        layout = inspect_nar_monthly_zip_structure(path)
        if layout.source_month != expected_month:
            raise UnsafeNarSource("NAR_DIAGNOSTIC_ARCHIVE_MONTH_MISMATCH")
    except (UnsafeNarSource, OSError, ValueError, RuntimeError, TypeError) as exc:
        return safe_failure("ZIP_METADATA", exc)

    try:
        month, texts = _read_nar_local_csv_texts(
            path, personal_private_permission_confirmed=True,
        )
        if month != expected_month:
            raise UnsafeNarSource("NAR_DIAGNOSTIC_ARCHIVE_MONTH_MISMATCH")
    except (UnsafeNarSource, OSError, ValueError, RuntimeError,
            UnicodeError, TypeError) as exc:
        return safe_failure("ZIP_CSV_READ", exc)

    try:
        coverage = audit_nar_monthly_coverage(texts, month=expected_month).summary
        status_report = audit_nar_official_exceptions(texts, month=expected_month)
        official = status_report.audit
        labels = derive_nar_status_aware_outcome_labels(status_report).audit
    except (UnsafeNarSource, OSError, ValueError, RuntimeError,
            UnicodeError, TypeError) as exc:
        return safe_failure("CSV_SCHEMA_OR_MONTH", exc)

    # Strictly aggregate-only payload: no keys, names, bytes or path are kept.
    return {
        "status": (
            "NAR_PRIVATE_MONTH_STRUCTURE_OK_PREOFF_UNVERIFIED"
            if coverage.complete_month_for_research
            else "NAR_PRIVATE_MONTH_REQUIRES_COVERAGE_REVIEW"
        ),
        "stage": "MONTH_COVERAGE",
        "month": expected_month,
        "observedRaces": coverage.observed_races,
        "acceptedFlatRaces": coverage.structurally_accepted_races,
        "acceptedFlatStarters": coverage.structurally_accepted_starters,
        "predeclaredOutOfScopeRaces": coverage.predeclared_out_of_scope_races,
        "unresolvedInScopeRaces": coverage.unresolved_in_scope_races,
        "staticReasonCounts": dict(coverage.exclusion_reasons),
        "completeMonth": coverage.complete_month_for_research,
        # New result-status interpretation is descriptive ONLY. It cannot
        # override the strict model-training / frozen-ticket ROI HOLD.
        "officialStatusAwareAudit": {
            "sourceRaces": official.source_races,
            "flatRaces": official.in_scope_flat_races,
            "baneiRaces": official.predeclared_banei_races,
            "validatedFlatRaces": official.status_validated_flat_races,
            "unresolvedFlatRaces": official.unresolved_flat_races,
            "horseStatusCounts": dict(official.status_horse_counts),
            "staticReasonCounts": dict(official.unresolved_reason_counts),
            "completeInterpretation": official.complete_flat_outcome_interpretation,
            "trainingAuthorized": False,
            "economicRoiAuthorized": False,
            "positiveEvDemonstrated": False,
            "sourceBytesExported": False,
        },
        "statusAwareLabelAudit": {
            "sourceRaces": labels.source_races,
            "flatRaces": labels.in_scope_flat_races,
            "validatedFlatRaces": labels.validated_flat_races,
            "unresolvedFlatRaces": labels.unresolved_flat_races,
            "observedRosterRows": labels.observed_roster_rows,
            "labeledRunnerRows": labels.labeled_runner_rows,
            "excludedScratchRows": labels.excluded_scratch_rows,
            "excludedRefundedRows": labels.excluded_refunded_rows,
            "unknownDisqualificationRows": labels.unknown_disqualification_rows,
            "officialStartedRows": labels.official_started_rows,
            "officialFinishedRows": labels.official_finished_rows,
            "preEventAvailabilityProven": False,
            "modelTrainingAuthorized": False,
            "realizedRoiAuthorized": False,
            "positiveEvDemonstrated": False,
            "sourceBytesExported": False,
        },
        "actualRightsIndependentlyVerified": False,
        "preEventSnapshotVerified": False,
        "modelTrainingExecuted": False,
        "sourceBytesUploaded": False,
        "protectedHoldoutOpened": False,
        "positiveEvDemonstrated": False,
        "approvedForPublication": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-monthly-race-zip", type=Path, required=True)
    parser.add_argument("--expected-month", required=True)
    parser.add_argument("--confirm-personal-private-nar-permission",
                        action="store_true")
    args = parser.parse_args()
    try:
        doc = diagnose_nar_month(
            args.local_monthly_race_zip,
            expected_month=args.expected_month,
            personal_private_permission_confirmed=(
                args.confirm_personal_private_nar_permission
            ),
        )
    except Exception:
        # Even a coding error must not print a full traceback or a path.
        doc = {
            "status": "NAR_PRIVATE_MONTH_DIAGNOSTIC_BLOCKED",
            "stage": "PRIVATE_PREFLIGHT",
            "reasonCode": "NAR_PRIVATE_DIAGNOSTIC_UNEXPECTED_FAILURE",
            "sourceBytesUploaded": False,
            "modelTrainingExecuted": False,
            "positiveEvDemonstrated": False,
            "protectedHoldoutOpened": False,
        }
    print(json.dumps(doc, sort_keys=True, ensure_ascii=False, allow_nan=False))
    return 0 if doc["status"] == "NAR_PRIVATE_MONTH_STRUCTURE_OK_PREOFF_UNVERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
