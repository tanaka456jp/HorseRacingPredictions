import argparse
import json
from pathlib import Path

from horse_racing_predictions.champion_calibration import (
    evaluate_temperature_calibration_predictions,
)
from horse_racing_predictions.champion_diagnostics import (
    build_frozen_champion_predictions,
    summarize_prediction_diagnostics,
)
from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the frozen Champion on post-training local history "
            "to diagnose confidence and selection thresholds."
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
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument(
        "--output",
        default="artifacts/champion_diagnostics/summary.json",
    )
    parser.add_argument(
        "--bankroll-yen",
        type=int,
        default=100_000,
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(args.champion)
    config = StrategyConfig()
    predictions = build_frozen_champion_predictions(
        history,
        champion,
        start_date=args.start.strip() or None,
        end_date=args.end.strip() or None,
    )
    summary = summarize_prediction_diagnostics(
        predictions,
        config=config,
        starting_bankroll_yen=args.bankroll_yen,
    )
    summary["champion"] = {
        "model_version": champion.manifest.model_version,
        "experiment_id": champion.manifest.experiment_id,
        "train_start": champion.manifest.train_start,
        "train_end": champion.manifest.train_end,
        "validation_research_roi": (
            champion.manifest.validation_research_roi
        ),
    }
    summary["temperature_calibration"] = (
        evaluate_temperature_calibration_predictions(
            predictions,
            champion,
            config=config,
        )
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({
        "status": summary["status"],
        "period": summary["period"],
        "rows": summary["rows"],
        "races": summary["races"],
        "selection_reason_counts": (
            summary["selection_reason_counts"]
        ),
        "race_confidence_quantiles": (
            summary["race_confidence_quantiles"]
        ),
        "current_config_backtest_final_odds": (
            summary["current_config_backtest_final_odds"]
        ),
        "temperature_calibration": {
            "temperature": summary[
                "temperature_calibration"
            ]["temperature"],
            "development_quality": summary[
                "temperature_calibration"
            ]["development"],
            "holdout_quality": summary[
                "temperature_calibration"
            ]["holdout"],
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
