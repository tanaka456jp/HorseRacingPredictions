import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from horse_racing_predictions.inference import (
    build_future_feature_frame,
)
from horse_racing_predictions.model_artifact import (
    ChampionManifest,
)


def _history():
    rows = []
    for day in range(1, 6):
        for horse in range(2):
            rows.append({
                "race_id": f"R{day}",
                "race_date": f"2021-07-0{day}",
                "horse_name": f"H{horse}",
                "finish_position": 1 if horse == day % 2 else 2,
                "win_odds": 2.0 + horse,
                "distance_m": 1600,
                "post_position": horse + 1,
                "age": 3,
                "carried_weight": 55 + horse,
                "horse_weight": 470 + horse * 10,
                "horse_weight_delta": 0,
                "racecourse": "Kyoto",
                "surface": "Turf",
                "weather": "Fine",
                "track_condition": "Good",
                "sex": "M",
                "jockey": f"J{horse}",
                "trainer": f"T{horse}",
            })
    return pd.DataFrame(rows)


def _entries():
    return pd.DataFrame([
        {
            "race_id": "F1",
            "race_date": "2021-07-10",
            "horse_name": "H0",
            "distance_m": 1600,
            "post_position": 1,
            "age": 3,
            "carried_weight": 55,
            "horse_weight": 472,
            "horse_weight_delta": 2,
            "racecourse": "Kyoto",
            "surface": "Turf",
            "weather": "Fine",
            "track_condition": "Good",
            "sex": "M",
            "jockey": "J0",
            "trainer": "T0",
        },
        {
            "race_id": "F1",
            "race_date": "2021-07-10",
            "horse_name": "H1",
            "distance_m": 1600,
            "post_position": 2,
            "age": 3,
            "carried_weight": 56,
            "horse_weight": 480,
            "horse_weight_delta": 0,
            "racecourse": "Kyoto",
            "surface": "Turf",
            "weather": "Fine",
            "track_condition": "Good",
            "sex": "M",
            "jockey": "J1",
            "trainer": "T1",
        },
    ])


def test_future_features_use_only_earlier_history():
    from horse_racing_predictions.features import build_pre_race_features

    history = _history()
    baseline = build_pre_race_features(history)
    future = build_future_feature_frame(
        history,
        _entries(),
        baseline.feature_columns,
    )

    assert len(future) == 2
    assert future["finish_position"].isna().all()
    assert set(baseline.feature_columns).issubset(future.columns)
    assert (future["horse_past_starts"] == 5).all()


def test_future_entries_must_be_after_history():
    from horse_racing_predictions.features import build_pre_race_features

    history = _history()
    entries = _entries()
    entries["race_date"] = "2021-07-05"
    baseline = build_pre_race_features(history)

    with pytest.raises(ValueError, match="strictly later"):
        build_future_feature_frame(
            history,
            entries,
            baseline.feature_columns,
        )


def test_champion_manifest_roundtrip_shape():
    manifest = ChampionManifest.create(
        feature_columns=["x", "surface"],
        categorical_columns=["surface"],
        train_start="2017-01-01",
        train_end="2021-07-31",
        source_id="test-source",
    )
    payload = json.loads(json.dumps({
        "model_version": manifest.model_version,
        "experiment_id": manifest.experiment_id,
        "model_kind": manifest.model_kind,
        "feature_columns": list(manifest.feature_columns),
        "categorical_columns": list(manifest.categorical_columns),
        "train_start": manifest.train_start,
        "train_end": manifest.train_end,
        "source_id": manifest.source_id,
        "validation_brier": manifest.validation_brier,
        "validation_log_loss": manifest.validation_log_loss,
        "validation_research_roi": manifest.validation_research_roi,
        "created_at": manifest.created_at,
    }))
    restored = ChampionManifest.from_dict(payload)
    assert restored.feature_columns == ("x", "surface")
    assert restored.model_version == "champion-v7"


def test_native_catboost_artifact_roundtrip_when_available(tmp_path):
    pytest.importorskip("catboost")
    from horse_racing_predictions.model_artifact import (
        load_champion_artifact,
        save_champion_artifact,
    )
    from horse_racing_predictions.modeling import CatBoostProbabilityModel

    train = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2", "R3", "R3"],
        "x": [0.0, 1.0, 1.0, 0.0, 0.2, 0.8],
        "surface": ["T", "T", "D", "D", "T", "T"],
        "is_winner": [1, 0, 0, 1, 1, 0],
    })
    model = CatBoostProbabilityModel(
        ["x", "surface"],
        iterations=10,
        depth=2,
    ).fit(train)
    before = model.predict_win_probability(train)

    manifest = ChampionManifest.create(
        feature_columns=model.feature_columns,
        categorical_columns=model.categorical_columns,
        train_start="2021-01-01",
        train_end="2021-01-03",
        source_id="test",
    )
    save_champion_artifact(model, manifest, tmp_path)
    loaded = load_champion_artifact(tmp_path)
    after = loaded.model.predict_win_probability(train)

    assert np.allclose(before.to_numpy(), after.to_numpy())
    assert (Path(tmp_path) / "model.cbm").exists()
    assert (Path(tmp_path) / "manifest.json").exists()
