import argparse
import json
from pathlib import Path

from horse_racing_predictions.jravan_incremental import (
    run_incremental_history_update,
)
from horse_racing_predictions.paper_settlement import (
    settle_paper_bets_from_csv,
    summary_to_dict,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Incrementally refresh local JRA-VAN completed history and "
            "settle any eligible Paper bets without full reacquisition."
        )
    )
    parser.add_argument(
        "--parsed",
        default="data/jravan/full/parsed_history.csv",
    )
    parser.add_argument(
        "--base",
        default="",
    )
    parser.add_argument(
        "--output-dir",
        default="data/jravan/full",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/jravan_incremental",
    )
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--overlap-days",
        type=int,
        default=7,
    )
    args = parser.parse_args()

    base = args.base.strip() or None
    incremental = run_incremental_history_update(
        parsed_path=args.parsed,
        base_path=base,
        output_dir=args.output_dir,
        artifact_dir=args.artifact_dir,
        overlap_days=args.overlap_days,
    )

    settlement = None
    ledger_path = Path(args.ledger)
    current_history = Path(args.output_dir) / "current_history.csv"
    if ledger_path.exists() and current_history.exists():
        settlement = settle_paper_bets_from_csv(
            ledger_path=ledger_path,
            history_path=current_history,
            source="JRA-VAN incremental canonical completed history",
        )

    payload = {
        "incremental": {
            "status": incremental.status,
            "existing_rows": incremental.existing_rows,
            "existing_races": incremental.existing_races,
            "existing_end": incremental.existing_end,
            "requested_from_time": incremental.requested_from_time,
            "raw_records": incremental.raw_records,
            "parsed_update_rows": incremental.parsed_update_rows,
            "parsed_update_races": incremental.parsed_update_races,
            "eligible_update_rows": incremental.eligible_update_rows,
            "eligible_update_races": incremental.eligible_update_races,
            "replaced_races": incremental.replaced_races,
            "merged_rows": incremental.merged_rows,
            "merged_races": incremental.merged_races,
            "merged_end": incremental.merged_end,
            "current_history_end": incremental.current_history_end,
            "winner_conflict_excluded_races": (
                incremental.winner_conflict_excluded_races
            ),
            "winner_conflict_excluded_rows": (
                incremental.winner_conflict_excluded_rows
            ),
        },
        "settlement": (
            summary_to_dict(settlement)
            if settlement is not None
            else {
                "status": "ledger_missing_or_no_current_history",
                "settled_now": 0,
            }
        ),
    }

    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / "incremental_settlement_summary.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
