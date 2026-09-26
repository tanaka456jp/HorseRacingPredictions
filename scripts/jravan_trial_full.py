import argparse

from horse_racing_predictions.jravan_trial import (
    run_jravan_trial_pipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run JRA-VAN history acquisition. Full setup is attempted "
            "first; free-trial -301 falls back to recent normal data."
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
    print(f"acquisition_mode={summary.acquisition_mode}")
    print(f"requested_from_time={summary.requested_from_time}")
    print(f"effective_from_time={summary.effective_from_time}")
    print(f"effective_option={summary.effective_option}")
    if summary.fallback_reason:
        print(f"WARNING: {summary.fallback_reason}")
    print(f"history_gap_days={summary.history_gap_days}")
    print(f"base_end={summary.base_end}")
    print(f"parsed_rows={summary.parsed_rows}")
    print(
        "supplemental_rows_after_base="
        f"{summary.supplemental_rows_after_base}"
    )
    print(
        "winner_conflict_excluded_races="
        f"{summary.winner_conflict_excluded_races}"
    )
    print(
        "winner_conflict_excluded_rows="
        f"{summary.winner_conflict_excluded_rows}"
    )
    print(f"zero_winner_races={summary.zero_winner_races}")
    print(
        "multiple_winner_races="
        f"{summary.multiple_winner_races}"
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
