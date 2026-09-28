import argparse
import json
from pathlib import Path

import pandas as pd

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.model_artifact import load_champion_artifact
from horse_racing_predictions.residual_v12_shadow import (
    build_residual_v12_shadow_predictions,
    capture_shadow_results_0b12,
    evaluate_shadow_results,
    summarize_shadow_predictions,
)
from horse_racing_predictions.residual_shadow_ledger import (
    ResidualShadowLedger,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Replay frozen Residual v12 as a shadow model using saved "
            "timestamped pre-race 0B31 odds. PaperBroker decisions are not changed."
        )
    )
    parser.add_argument("--history", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--odds", required=True)
    parser.add_argument("--champion", required=True)
    parser.add_argument(
        "--predictions-output",
        default="data/jravan/forward/residual_v12_shadow_predictions.csv",
    )
    parser.add_argument(
        "--summary-output",
        default="artifacts/residual_v12_shadow/summary.json",
    )
    parser.add_argument(
        "--ledger",
        default="data/jravan/forward/residual_v12_shadow.sqlite3",
    )
    args = parser.parse_args()

    history = read_csv_flexible(args.history, low_memory=False)
    entries = pd.read_csv(args.entries, encoding="utf-8-sig")
    odds = pd.read_csv(args.odds, encoding="utf-8-sig")
    champion = load_champion_artifact(args.champion)

    predictions = build_residual_v12_shadow_predictions(
        history,
        entries,
        odds,
        champion,
    )

    predictions_path = Path(args.predictions_output)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(
        predictions_path,
        index=False,
        encoding="utf-8-sig",
    )

    prediction_summary = summarize_shadow_predictions(
        predictions
    )
    results, realtime_errors = capture_shadow_results_0b12(
        predictions
    )
    evaluation = evaluate_shadow_results(
        predictions,
        results,
    )

    ledger = ResidualShadowLedger(args.ledger)
    try:
        newly_recorded_predictions = (
            ledger.record_predictions(predictions)
        )
        newly_recorded_results = (
            ledger.record_results(results)
        )
        cumulative = ledger.cumulative_summary()
    finally:
        ledger.close()

    payload = {
        "status": (
            "evaluated"
            if evaluation["status"] == "evaluated"
            else "predicted_pending_results"
        ),
        "prediction_summary": prediction_summary,
        "result_fetch_errors": int(realtime_errors),
        "evaluation": evaluation,
        "ledger_update": {
            "new_prediction_rows": int(
                newly_recorded_predictions
            ),
            "new_result_rows": int(
                newly_recorded_results
            ),
        },
        "cumulative": cumulative,
        "paper_broker_unchanged": True,
        "uses_timestamped_prerace_odds": True,
        "uses_final_odds_for_shadow_inference": False,
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
