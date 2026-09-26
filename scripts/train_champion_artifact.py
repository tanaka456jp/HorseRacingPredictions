import argparse
from pathlib import Path

import kagglehub
import pandas as pd

from horse_racing_predictions.data_sources import load_jra_history_csv
from horse_racing_predictions.features import build_pre_race_features
from horse_racing_predictions.model_artifact import (
    ChampionManifest,
    save_champion_artifact,
)
from horse_racing_predictions.modeling import CatBoostProbabilityModel


DATASET_HANDLE = "takamotoki/jra-horse-racing-dataset"
RACE_RESULT_FILE = "19860105-20210731_race_result.csv"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2017-01-01")
    parser.add_argument("--end", default="2021-07-31")
    parser.add_argument(
        "--output-dir",
        default="artifacts/champion_v7",
    )
    args = parser.parse_args()

    Path("data/raw").mkdir(parents=True, exist_ok=True)
    downloaded = kagglehub.dataset_download(
        DATASET_HANDLE,
        path=RACE_RESULT_FILE,
        output_dir="data/raw",
    )
    history = load_jra_history_csv(
        _resolve_downloaded_file(downloaded)
    )
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

    built = build_pre_race_features(history)
    model = CatBoostProbabilityModel(
        list(built.feature_columns)
    ).fit(
        built.frame,
        target_col="is_winner",
    )

    manifest = ChampionManifest.create(
        feature_columns=built.feature_columns,
        categorical_columns=model.categorical_columns,
        train_start=str(history["race_date"].min().date()),
        train_end=str(history["race_date"].max().date()),
        source_id=DATASET_HANDLE,
    )
    output = save_champion_artifact(
        model,
        manifest,
        args.output_dir,
    )
    print(output)


if __name__ == "__main__":
    main()
