import argparse
import json
from dataclasses import asdict
from pathlib import Path

from horse_racing_predictions.jravan import export_race_raw
from horse_racing_predictions.jravan_doctor import (
    run_jravan_doctor,
    write_doctor_report,
)
from horse_racing_predictions.jravan_parser import (
    convert_raw_jsonl,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run JV-Link doctor, capture a bounded RA/SE sample, "
            "and parse it to canonical history."
        )
    )
    parser.add_argument(
        "--from-time",
        default="20210801000000",
    )
    parser.add_argument(
        "--option",
        type=int,
        choices=(1, 2, 3, 4),
        default=4,
    )
    parser.add_argument(
        "--doctor-records",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--sample-records",
        type=int,
        default=5000,
    )
    parser.add_argument(
        "--output-dir",
        default="data/jravan/smoke",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/jravan_smoke",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    artifact_dir = Path(args.artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    doctor = run_jravan_doctor(
        from_time="00000000000000",
        option=2,
        max_records=args.doctor_records,
    )
    write_doctor_report(
        doctor,
        artifact_dir / "doctor.json",
    )
    if not doctor.ready:
        raise SystemExit(2)

    raw_summary = export_race_raw(
        output_path=output_dir / "race_raw.jsonl",
        summary_path=artifact_dir / "raw_summary.json",
        from_time=args.from_time,
        option=args.option,
        record_types={"RA", "SE"},
        max_records=args.sample_records,
    )

    parse_report = convert_raw_jsonl(
        input_path=output_dir / "race_raw.jsonl",
        output_path=output_dir / "canonical_history.csv",
        report_path=artifact_dir / "parse_report.json",
    )

    result = {
        "status": (
            "ready"
            if parse_report.output_rows > 0
            else "blocked_no_completed_rows"
        ),
        "doctor": asdict(doctor),
        "raw": asdict(raw_summary),
        "parse": asdict(parse_report),
        "canonical_history": str(
            output_dir / "canonical_history.csv"
        ),
    }
    (artifact_dir / "smoke_summary.json").write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"status={result['status']}")
    print(f"raw_records={raw_summary.records_written}")
    print(f"history_rows={parse_report.output_rows}")
    print(f"history_races={parse_report.output_races}")
    if result["status"] != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
