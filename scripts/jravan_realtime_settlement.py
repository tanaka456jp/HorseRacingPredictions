import argparse
import json
from pathlib import Path

from horse_racing_predictions.jravan_realtime_settlement import (
    run_realtime_paper_settlement,
    summary_to_dict,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Settle eligible Paper win bets from JRA-VAN 0B12 "
            "completed-race realtime data."
        )
    )
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--output",
        default="artifacts/jravan_realtime_settlement/summary.json",
    )
    args = parser.parse_args()

    summary = run_realtime_paper_settlement(
        ledger_path=args.ledger,
    )
    payload = summary_to_dict(summary)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
