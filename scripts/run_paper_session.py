import argparse
import json
from pathlib import Path

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.paper_cli import run_paper_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run timestamped Paper Trading decisions from CSV."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--output",
        default="artifacts/paper_session_summary.json",
    )
    parser.add_argument("--bankroll-yen", type=int, default=100_000)
    parser.add_argument("--min-ev", type=float, default=1.15)
    parser.add_argument(
        "--min-probability",
        type=float,
        default=0.03,
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.55,
    )
    args = parser.parse_args()

    config = StrategyConfig(
        min_ev=args.min_ev,
        min_probability=args.min_probability,
        min_confidence=args.min_confidence,
    )
    result = run_paper_csv(
        args.input,
        args.ledger,
        args.bankroll_yen,
        config=config,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
