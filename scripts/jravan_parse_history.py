import argparse

from horse_racing_predictions.jravan_parser import (
    convert_raw_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert local JRA-VAN RA/SE raw JSONL into canonical "
            "completed-race history."
        )
    )
    parser.add_argument(
        "--input",
        default="data/jravan/race_raw.jsonl",
    )
    parser.add_argument(
        "--output",
        default="data/jravan/current_history_supplement.csv",
    )
    parser.add_argument(
        "--report",
        default="artifacts/jravan_parse_report.json",
    )
    parser.add_argument(
        "--include-non-jra",
        action="store_true",
        help="Keep local/overseas records instead of JRA courses 01-10 only.",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="Keep SE rows without final finish/valid win odds.",
    )
    args = parser.parse_args()

    report = convert_raw_jsonl(
        input_path=args.input,
        output_path=args.output,
        report_path=args.report,
        jra_only=not args.include_non_jra,
        completed_only=not args.include_incomplete,
    )

    print(f"spec_version={report.spec_version}")
    print(f"raw_records={report.raw_records}")
    print(f"output_rows={report.output_rows}")
    print(f"output_races={report.output_races}")
    for warning in report.warnings:
        print(f"WARNING: {warning}")

    if report.output_rows == 0:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
