import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.market_aware_ranker_v11 import (
    evaluate_market_aware_ranker_v11_development,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate market-aware Ranker v11 on development-only history. "
            "2025+ rows are excluded before feature construction."
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
        default="artifacts/market_aware_ranker_v11/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_market_aware_ranker_v11_development(
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
        "features": result["features"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
