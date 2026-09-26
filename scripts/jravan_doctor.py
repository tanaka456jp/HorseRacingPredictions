import argparse

from horse_racing_predictions.jravan_doctor import (
    run_jravan_doctor,
    write_doctor_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose local Windows JV-Link connectivity."
    )
    parser.add_argument(
        "--from-time",
        default="00000000000000",
    )
    parser.add_argument(
        "--option",
        type=int,
        choices=(1, 2, 3, 4),
        default=2,
    )
    parser.add_argument(
        "--sid",
        default="UNKNOWN",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--output",
        default="artifacts/jravan_doctor.json",
    )
    args = parser.parse_args()

    report = run_jravan_doctor(
        from_time=args.from_time,
        option=args.option,
        sid=args.sid,
        max_records=args.max_records,
    )
    write_doctor_report(report, args.output)

    print(f"status={report.status}")
    print(f"python={report.python_version} ({report.python_bits}bit)")
    print(f"initialized={report.initialized}")
    print(f"status_before_open={report.status_before_open}")
    print(f"JVOpen={report.open_return_code}")
    print(f"read_count={report.read_count}")
    print(f"download_count={report.download_count}")
    print(f"sample_records={report.sample_records}")
    print(
        "record_types="
        + ",".join(
            f"{key}:{value}"
            for key, value in report.record_type_counts.items()
        )
    )
    for message in report.errors:
        print(f"ERROR: {message}")
    for message in report.guidance:
        print(f"GUIDANCE: {message}")

    if not report.ready:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
