import argparse
from datetime import datetime

from horse_racing_predictions.current_history import (
    HistorySourceManifest,
    prepare_current_history,
)


def _parse_datetime(value: str | None):
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and append approved supplemental race history "
            "without scraping an unapproved source."
        )
    )
    parser.add_argument("--base", required=True)
    parser.add_argument("--supplement", required=True)
    parser.add_argument(
        "--output",
        default="data/curated/current_history.csv",
    )
    parser.add_argument(
        "--manifest-output",
        default="artifacts/current_history_manifest.json",
    )
    parser.add_argument(
        "--report-output",
        default="artifacts/current_history_report.json",
    )
    parser.add_argument("--source-name", required=True)
    parser.add_argument(
        "--source-kind",
        choices=(
            "user_supplied",
            "approved_free_provider",
            "licensed_provider",
        ),
        required=True,
    )
    parser.add_argument(
        "--source-reference",
        default="",
    )
    parser.add_argument("--rights-note", required=True)
    parser.add_argument(
        "--acquired-at",
        help="Timezone-aware ISO timestamp.",
    )
    parser.add_argument(
        "--approved-for-modeling",
        action="store_true",
    )
    parser.add_argument(
        "--raw-redistribution-allowed",
        action="store_true",
    )
    parser.add_argument(
        "--max-gap-days",
        type=int,
        default=14,
    )
    parser.add_argument(
        "--allow-gap",
        action="store_true",
        help=(
            "Allow a history gap larger than max-gap-days. "
            "The gap is still recorded as a warning."
        ),
    )
    args = parser.parse_args()

    manifest = HistorySourceManifest.create(
        source_name=args.source_name,
        source_kind=args.source_kind,
        source_reference=args.source_reference,
        rights_note=args.rights_note,
        approved_for_modeling=args.approved_for_modeling,
        raw_redistribution_allowed=(
            args.raw_redistribution_allowed
        ),
        acquired_at=_parse_datetime(
            args.acquired_at
        ),
    )

    report = prepare_current_history(
        base_path=args.base,
        supplemental_path=args.supplement,
        output_path=args.output,
        manifest_path=args.manifest_output,
        report_path=args.report_output,
        manifest=manifest,
        max_gap_days=args.max_gap_days,
        allow_gap=args.allow_gap,
    )

    print(f"status={report.status}")
    print(f"base_end={report.base_end}")
    print(f"supplemental_start={report.supplemental_start}")
    print(f"supplemental_end={report.supplemental_end}")
    print(f"gap_days={report.gap_days}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")
    for error in report.errors:
        print(f"ERROR: {error}")

    if not report.ready:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
