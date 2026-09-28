import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.market_residual_v12 import (
    evaluate_market_residual_v12_development,
)
from horse_racing_predictions.model_artifact import load_champion_artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Train a market residual model on the original training period, "
            "fit correction strength through 2022, and validate unchanged on "
            "2023 and 2024. 2025+ remains untouched."
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
        default="artifacts/market_residual_v12/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_market_residual_v12_development(
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
        "gamma_tuning": {
            "period_start": result["gamma_tuning"]["period_start"],
            "period_end": result["gamma_tuning"]["period_end"],
            "rows": result["gamma_tuning"]["rows"],
            "races": result["gamma_tuning"]["races"],
            "selected_gamma": result["gamma_tuning"]["selected_gamma"],
        },
        "validation_2023": result["validation_2023"],
        "validation_2024": result["validation_2024"],
        "development_gate_passed": result["development_gate_passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
