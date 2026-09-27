import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.market_overlay_research import (
    evaluate_market_overlay_v11_development,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fit a market-overlay rule on 2023 development data and "
            "validate the unchanged rule on 2024. 2025+ remains untouched."
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
        default="artifacts/market_overlay_v11/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_market_overlay_v11_development(
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
        "tuning_2023": {
            "period_start": result["tuning_2023"]["period_start"],
            "period_end": result["tuning_2023"]["period_end"],
            "rows": result["tuning_2023"]["rows"],
            "races": result["tuning_2023"]["races"],
            "fitted_rule": result["tuning_2023"]["fitted_rule"],
        },
        "validation_2024": result["validation_2024"],
        "constraints": result["constraints"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
