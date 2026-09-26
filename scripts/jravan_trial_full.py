import argparse

from horse_racing_predictions.jravan_trial import (
    run_jravan_trial_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full JRA-VAN free-trial acquisition pipeline "
            "from JV-Link through Current History Intake."
        )
    )
    parser.add_argument(
        "--base",
        help=(
            "Optional approved base history CSV ending 2021-07-31. "
            "If omitted, the approved Kaggle base is downloaded automatically."
        ),
    )
    parser.add_argument(
        "--from-time",
        default="20210801000000",
    )
    parser.add_argument(
        "--option",
        type=int,
        choices=(3, 4),
        default=4,
    )
    parser.add_argument(
        "--output-dir",
        default="data/jravan/full",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/jravan_full",
    )
    args = parser.parse_args()

    summary = run_jravan_trial_pipeline(
        base_path=args.base,
        output_dir=args.output_dir,
        artifact_dir=args.artifact_dir,
        from_time=args.from_time,
        option=args.option,
    )

    print(f"status={summary.status}")
    print(f"base_end={summary.base_end}")
    print(f"parsed_rows={summary.parsed_rows}")
    print(
        "supplemental_rows_after_base="
        f"{summary.supplemental_rows_after_base}"
    )
    print(
        f"supplemental_period={summary.supplemental_start}"
        f"..{summary.supplemental_end}"
    )
    print(
        f"current_history_end={summary.current_history_end}"
    )


if __name__ == "__main__":
    main()
