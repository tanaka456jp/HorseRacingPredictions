import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import (
    read_csv_flexible,
)
from horse_racing_predictions.market_blend_research import (
    evaluate_market_blend_history,
)
from horse_racing_predictions.model_artifact import (
    load_champion_artifact,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fit a calibrated Champion/market probability blend on "
            "development history and evaluate it on untouched holdout."
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
        default="artifacts/market_blend_research/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    champion = load_champion_artifact(
        args.champion,
    )
    result = evaluate_market_blend_history(
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
        "development": {
            "period_start": result["development"]["period_start"],
            "period_end": result["development"]["period_end"],
            "rows": result["development"]["rows"],
            "races": result["development"]["races"],
            "temperature": result["development"]["temperature"],
            "fitted_alpha_model_weight": (
                result["development"][
                    "fitted_alpha_model_weight"
                ]
            ),
        },
        "holdout": {
            "period_start": result["holdout"]["period_start"],
            "period_end": result["holdout"]["period_end"],
            "rows": result["holdout"]["rows"],
            "races": result["holdout"]["races"],
            "quality": result["holdout"]["quality"],
            "fitted_blend_beats_market_winner_log_loss": (
                result["holdout"][
                    "fitted_blend_beats_market_winner_log_loss"
                ]
            ),
            "winner_log_loss_delta_vs_market": (
                result["holdout"][
                    "winner_log_loss_delta_vs_market"
                ]
            ),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
