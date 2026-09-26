import argparse

from horse_racing_predictions.jravan_trial import (
    resume_current_history_from_parsed,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Resume JRA-VAN Current History Intake from an existing "
            "data/jravan/full/parsed_history.csv without reacquiring JV-Link data."
        )
    )
    parser.add_argument(
        "--base",
        help=(
            "Optional approved base history CSV. If omitted, the approved "
            "1986-2021 Kaggle base is resolved automatically."
        ),
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

    summary = resume_current_history_from_parsed(
        base_path=args.base,
        output_dir=args.output_dir,
        artifact_dir=args.artifact_dir,
    )

    print(f"status={summary.status}")
    print(f"acquisition_mode={summary.acquisition_mode}")
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
