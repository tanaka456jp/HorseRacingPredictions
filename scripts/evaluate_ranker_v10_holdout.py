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
    evaluate_ranker_v10_holdout_confirmation,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Confirm the fixed Ranker v10 context feature set on the "
            "untouched 2025-2026 holdout."
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
        default="artifacts/ranker_v10_holdout/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_ranker_v10_holdout_confirmation(
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
        "holdout_2025_2026": (
            result["holdout_2025_2026"]
        ),
        "features": {
            "v9_count": result["features"]["v9_count"],
            "v10_count": result["features"]["v10_count"],
            "added_count": result["features"]["added_count"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
