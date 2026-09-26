import argparse
from pathlib import Path

from horse_racing_predictions.data_sources import (
    load_future_entries_csv,
    load_jra_history_csv,
)
from horse_racing_predictions.inference import predict_future_entries
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Champion probabilities for future races."
    )
    parser.add_argument("--history", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument(
        "--output",
        default="artifacts/future_predictions.csv",
    )
    args = parser.parse_args()

    champion = load_champion_artifact(args.artifact_dir)
    history = load_jra_history_csv(args.history)
    entries = load_future_entries_csv(args.entries)
    prediction = predict_future_entries(
        champion,
        history,
        entries,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    prediction.to_csv(
        output,
        index=False,
        encoding="utf-8-sig",
    )
    print(output)


if __name__ == "__main__":
    main()
