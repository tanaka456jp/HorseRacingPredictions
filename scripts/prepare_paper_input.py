import argparse
from datetime import datetime

from horse_racing_predictions.paper_input import (
    prepare_paper_input_files,
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
        description="Join Champion predictions to pre-race odds snapshots."
    )
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--odds", required=True)
    parser.add_argument(
        "--output",
        default="artifacts/paper_input.csv",
    )
    parser.add_argument(
        "--decision-time",
        help="Timezone-aware ISO timestamp. Defaults to current UTC time.",
    )
    args = parser.parse_args()

    output = prepare_paper_input_files(
        args.predictions,
        args.odds,
        args.output,
        decision_time=_parse_datetime(args.decision_time),
    )
    print(output)


if __name__ == "__main__":
    main()
