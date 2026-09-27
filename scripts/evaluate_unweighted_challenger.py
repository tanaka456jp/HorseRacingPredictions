import argparse
import json
from pathlib import Path

from horse_racing_predictions.challenger_research import (
    evaluate_unweighted_catboost_challenger,
)
from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compare the frozen Balanced Champion with an otherwise "
            "matched unweighted CatBoost challenger on post-training "
            "development and untouched holdout history."
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
        default="artifacts/champion_challenger/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_unweighted_catboost_challenger(
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
        "evaluation": result["evaluation"],
        "holdout_comparison": (
            result["holdout_comparison"]
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
