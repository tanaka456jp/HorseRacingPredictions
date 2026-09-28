import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.market_residual_v12_holdout import (
    evaluate_market_residual_v12_holdout,
)
from horse_racing_predictions.model_artifact import load_champion_artifact


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Confirm frozen market residual v12 on the untouched "
            "2025-2026 holdout using fixed gamma=4.0."
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
        default="artifacts/market_residual_v12_holdout/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(args.history, low_memory=False)
    champion = load_champion_artifact(args.champion)
    result = evaluate_market_residual_v12_holdout(
        history,
        champion,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "training": result["training"],
        "fixed_parameters": result["fixed_parameters"],
        "holdout_combined": result["holdout_combined"],
        "holdout_yearly": result["holdout_yearly"],
        "confirmation_gate_passed": result["confirmation_gate_passed"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
