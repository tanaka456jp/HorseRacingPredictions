import argparse
import json
import traceback
from dataclasses import asdict
from pathlib import Path

from horse_racing_predictions.jravan import export_race_raw
from horse_racing_predictions.jravan_parser import (
    convert_raw_jsonl,
)


def _write_smoke_error(artifact_dir: Path, exc: BaseException) -> None:
    payload = {
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }
    (artifact_dir / "smoke_error.json").write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Capture one bounded current-week RA/SE sample and "
            "verify official-spec parsing, even when races are not final."
        )
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

    try:
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
            output_path=output_dir / "parsed_sample.csv",
            report_path=artifact_dir / "parse_report.json",
            completed_only=False,
        )

        result = {
            "status": (
                "ready"
                if parse_report.output_rows > 0
                else "blocked_no_matched_rows"
            ),
            "raw": asdict(raw_summary),
            "parse": asdict(parse_report),
            "parsed_sample": str(
                output_dir / "parsed_sample.csv"
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
        print(f"parsed_rows={parse_report.output_rows}")
        print(f"parsed_races={parse_report.output_races}")
        print(
            "selected_ra_records="
            f"{parse_report.selected_ra_records}"
        )
        print(
            "selected_se_records="
            f"{parse_report.selected_se_records}"
        )
        if result["status"] != "ready":
            raise RuntimeError(
                "RA/SE smoke produced no matched parsable rows"
            )
    except Exception as exc:
        _write_smoke_error(artifact_dir, exc)
        print(
            f"ERROR: {type(exc).__name__}: {exc}",
            flush=True,
        )
        raise


if __name__ == "__main__":
    main()
