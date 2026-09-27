import argparse
import json
from pathlib import Path

from horse_racing_predictions.paper_settlement import (
    settle_paper_bets_from_csv,
    summary_to_dict,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Settle auditable Paper win bets from completed canonical "
            "JRA race history. Incomplete/ambiguous results remain pending."
        )
    )
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument("--history", required=True)
    parser.add_argument(
        "--source",
        default="JRA-VAN canonical completed history",
    )
    parser.add_argument(
        "--output",
        default="artifacts/paper_settlement_summary.json",
    )
    args = parser.parse_args()

    summary = settle_paper_bets_from_csv(
        ledger_path=args.ledger,
        history_path=args.history,
        source=args.source,
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
