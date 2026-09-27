import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)
from horse_racing_predictions.ranker_v10_research import (
    evaluate_ranker_v10_development,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Ranker v9 with experimental context-feature "
            "Ranker v10 using development data only."
        )
    )
    parser.add_argument(
        "--history",
        default="data/jravan/full/current_history.csv",
    )
    parser.add_argument(
        "--champion",
        default="artifacts/champion_v7",
    )
    parser.add_argument(
        "--output",
        default="artifacts/ranker_v10_development/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_ranker_v10_development(
        history,
        champion,
    )

    output = Path(args.output)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "training": result["training"],
        "calibration": result["calibration"],
        "selection_2024": result["selection_2024"],
        "features": {
            "v9_count": result["features"]["v9_count"],
            "v10_count": result["features"]["v10_count"],
            "added_count": result["features"]["added_count"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
