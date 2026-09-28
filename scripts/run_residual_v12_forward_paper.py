import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.model_artifact import load_champion_artifact
from horse_racing_predictions.residual_shadow_paper import (
    run_residual_v12_forward_paper,
)
from horse_racing_predictions.residual_v12_shadow import (
    build_residual_v12_shadow_predictions,
    summarize_shadow_predictions,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run frozen Residual v12 prospectively on an already-captured "
            "pre-race 0B31 snapshot and record PaperBroker-only decisions."
        )
    )
    parser.add_argument("--history", required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--odds", required=True)
    parser.add_argument("--champion", required=True)
    parser.add_argument(
        "--paper-ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--paper-bankroll-yen",
        type=int,
        default=100_000,
    )
    parser.add_argument(
        "--residual-model-cache",
        default="artifacts/residual_v12_frozen_model",
    )
    parser.add_argument(
        "--predictions-output",
        default=(
            "data/jravan/forward/"
            "residual_v12_forward_paper_predictions.csv"
        ),
    )
    parser.add_argument(
        "--summary-output",
        default="artifacts/residual_v12_forward_paper/summary.json",
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
        model_cache_dir=args.residual_model_cache,
    )

    predictions_path = Path(args.predictions_output)
    predictions_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(
        predictions_path,
        index=False,
        encoding="utf-8-sig",
    )

    prediction_summary = summarize_shadow_predictions(predictions)
    decision_time = datetime.now(timezone.utc)
    paper_forward = run_residual_v12_forward_paper(
        predictions,
        ledger_path=args.paper_ledger,
        bankroll_yen=args.paper_bankroll_yen,
        decision_time=decision_time,
    )

    payload = {
        "status": paper_forward["status"],
        "decision_time": decision_time.isoformat(),
        "prediction_summary": prediction_summary,
        "paper_forward": paper_forward,
        "result_reconciliation_executed": False,
        "uses_timestamped_prerace_odds": True,
        "uses_final_odds_for_inference": False,
        "historical_forward_rows_backfilled": False,
        "live_execution_enabled": False,
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
