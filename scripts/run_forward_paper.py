import argparse
from datetime import datetime

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.forward_pipeline import (
    run_forward_paper_pipeline,
)


def _parse_datetime(value: str | None):
    if value is None:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate Champion probabilities, join timestamped odds, "
            "and run Paper Trading in one command."
        )
    )
    parser.add_argument("--history", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--odds", required=True)
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/forward_paper",
    )
    parser.add_argument("--bankroll-yen", type=int, default=100_000)
    parser.add_argument("--decision-time")
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

    result = run_forward_paper_pipeline(
        history_path=args.history,
        entries_path=args.entries,
        artifact_dir=args.artifact_dir,
        odds_path=args.odds,
        ledger_path=args.ledger,
        output_dir=args.output_dir,
        bankroll_yen=args.bankroll_yen,
        decision_time=_parse_datetime(args.decision_time),
        config=config,
    )
    print(result["summary_file"])


if __name__ == "__main__":
    main()
