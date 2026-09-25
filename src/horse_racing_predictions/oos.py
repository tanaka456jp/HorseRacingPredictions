from dataclasses import dataclass
import math
import pandas as pd

from .leakage import assert_leakage_safe
from .modeling import BaselineProbabilityModel
from .walkforward import expanding_walk_forward_splits

@dataclass(frozen=True)
class OOSResult:
    predictions: pd.DataFrame
    fold_count: int

def _race_certainty(probabilities: pd.Series) -> float:
    p = probabilities[probabilities > 0].astype(float)
    n = len(p)
    if n <= 1:
        return 1.0
    entropy = -float((p * p.map(math.log)).sum())
    maximum = math.log(n)
    if maximum <= 0:
        return 1.0
    return max(0.0, min(1.0, 1.0 - entropy / maximum))

def generate_walk_forward_predictions(
    frame: pd.DataFrame,
    feature_columns: list[str] | tuple[str, ...],
    min_train_dates: int = 30,
    test_dates: int = 7,
    gap_dates: int = 0,
    model_version: str = "baseline-logit-v0",
) -> OOSResult:
    feature_columns = list(feature_columns)
    assert_leakage_safe(feature_columns)

    required = {
        "race_id",
        "race_date",
        "horse_name",
        "finish_position",
        "win_odds",
        "is_winner",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing OOS columns: {sorted(missing)}")

    outputs = []
    fold_count = 0

    for fold_number, fold in enumerate(
        expanding_walk_forward_splits(
            frame,
            "race_date",
            min_train_dates=min_train_dates,
            test_dates=test_dates,
            gap_dates=gap_dates,
        ),
        start=1,
    ):
        train = frame.loc[fold.train_index].copy()
        test = frame.loc[fold.test_index].copy()

        model = BaselineProbabilityModel(feature_columns).fit(
            train,
            target_col="is_winner",
        )
        probability = model.predict_win_probability(
            test,
            race_col="race_id",
        )

        out = test[
            ["race_id", "race_date", "horse_name", "finish_position", "win_odds"]
        ].copy()
        if "post_position" in test.columns:
            out["horse_id"] = (
                test["race_id"].astype(str)
                + "-"
                + test["post_position"].astype(str)
            )
        else:
            out["horse_id"] = (
                test["race_id"].astype(str)
                + "-"
                + test.groupby("race_id").cumcount().add(1).astype(str)
            )

        out["predicted_win_probability"] = probability
        out["decimal_odds"] = pd.to_numeric(
            out["win_odds"], errors="coerce"
        )
        out["model_version"] = f"{model_version}-fold{fold_number}"
        out["fold_number"] = fold_number
        out["train_end"] = fold.train_end
        out["test_start"] = fold.test_start

        certainty = probability.groupby(test["race_id"]).transform(
            _race_certainty
        )
        out["confidence"] = certainty
        outputs.append(out)
        fold_count += 1

    if not outputs:
        columns = [
            "race_id", "race_date", "horse_name", "finish_position",
            "win_odds", "horse_id", "predicted_win_probability",
            "decimal_odds", "model_version", "fold_number",
            "train_end", "test_start", "confidence",
        ]
        return OOSResult(pd.DataFrame(columns=columns), 0)

    predictions = pd.concat(outputs, ignore_index=True)
    return OOSResult(predictions=predictions, fold_count=fold_count)
