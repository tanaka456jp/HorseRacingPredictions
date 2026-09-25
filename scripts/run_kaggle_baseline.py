import argparse
import json
from dataclasses import asdict
from pathlib import Path

import kagglehub
import pandas as pd

from horse_racing_predictions.backtest import simulate_win_strategy
from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.data_sources import load_jra_history_csv
from horse_racing_predictions.evaluation import brier_score, binary_log_loss
from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.oos import generate_walk_forward_predictions
from horse_racing_predictions.validation import FINAL_WIN_ODDS

DATASET_HANDLE = "takamotoki/jra-horse-racing-dataset"
RACE_RESULT_FILE = "19860105-20210731_race_result.csv"
EXPERIMENT_ID = "v4-forward-temperature-calibration"

def _resolve_downloaded_file(downloaded: str | Path) -> Path:
    path = Path(downloaded)
    if path.is_file():
        return path
    direct = path / RACE_RESULT_FILE
    if direct.exists():
        return direct
    matches = list(path.rglob(RACE_RESULT_FILE))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"could not uniquely locate {RACE_RESULT_FILE}: {matches}"
        )
    return matches[0]

def _market_implied_probability(frame: pd.DataFrame) -> pd.Series:
    odds = pd.to_numeric(frame["decimal_odds"], errors="coerce")
    inverse = 1.0 / odds.where(odds > 1.0)
    denominator = inverse.groupby(frame["race_id"]).transform("sum")
    return (inverse / denominator).fillna(0.0)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default="2021-07-31")
    parser.add_argument("--min-train-dates", type=int, default=120)
    parser.add_argument("--test-dates", type=int, default=20)
    parser.add_argument("--calibration-dates", type=int, default=20)
    parser.add_argument("--ev-threshold", type=float, default=1.15)
    parser.add_argument(
        "--output",
        default="artifacts/kaggle_baseline_summary.json",
    )
    args = parser.parse_args()

    Path("data/raw").mkdir(parents=True, exist_ok=True)
    downloaded = kagglehub.dataset_download(
        DATASET_HANDLE,
        path=RACE_RESULT_FILE,
        output_dir="data/raw",
    )
    csv_path = _resolve_downloaded_file(downloaded)

    history = load_jra_history_csv(csv_path)
    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)
    history = history[
        (history["race_date"] >= start)
        & (history["race_date"] <= end)
    ].copy()
    history = history.dropna(
        subset=["finish_position", "win_odds"]
    )
    history = history[history["win_odds"] > 1.0].copy()

    features = build_pre_race_features(history)
    oos = generate_walk_forward_predictions(
        features.frame,
        features.feature_columns,
        min_train_dates=args.min_train_dates,
        test_dates=args.test_dates,
        model_version=EXPERIMENT_ID,
        calibration_dates=args.calibration_dates,
    )
    pred = oos.predictions.copy()
    if pred.empty:
        raise RuntimeError("walk-forward produced no OOS predictions")

    pred["is_winner"] = pred["finish_position"].eq(1).astype(int)
    market_p = _market_implied_probability(pred)

    model_brier = brier_score(
        pred["predicted_win_probability"],
        pred["is_winner"],
    )
    model_log_loss = binary_log_loss(
        pred["predicted_win_probability"],
        pred["is_winner"],
    )
    market_brier = brier_score(
        market_p,
        pred["is_winner"],
    )
    market_log_loss = binary_log_loss(
        market_p,
        pred["is_winner"],
    )

    _, backtest = simulate_win_strategy(
        pred,
        starting_bankroll_yen=100_000,
        config=StrategyConfig(
            min_ev=args.ev_threshold,
            min_confidence=0.0,
        ),
        odds_evidence=FINAL_WIN_ODDS,
    )

    result = {
        "experiment_id": EXPERIMENT_ID,
        "source": {
            "dataset": DATASET_HANDLE,
            "file": RACE_RESULT_FILE,
            "raw_data_redistributed": False,
        },
        "period": {
            "start": str(pred["race_date"].min().date()),
            "end": str(pred["race_date"].max().date()),
        },
        "rows": int(len(pred)),
        "races": int(pred["race_id"].nunique()),
        "folds": int(oos.fold_count),
        "calibration_dates": args.calibration_dates,
        "temperature": {
            "min": float(pred["temperature"].min()),
            "median": float(pred["temperature"].median()),
            "max": float(pred["temperature"].max()),
        },
        "feature_columns": list(features.feature_columns),
        "probability_quality": {
            "model_brier": model_brier,
            "market_brier": market_brier,
            "model_log_loss": model_log_loss,
            "market_log_loss": market_log_loss,
        },
        "betting": asdict(backtest),
        "interpretation": {
            "roi_status": (
                "research_only"
                if not backtest.roi_verified
                else "verified"
            ),
            "warning": (
                "Final historical win odds are used for EV selection. "
                "This is not forward-captured pre-race odds, so ROI must "
                "not be treated as verified live profitability."
            ),
        },
    }

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
