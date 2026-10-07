from pathlib import Path

import numpy as np
import pandas as pd

from horse_racing_predictions.exotic_longshot_phase7 import (
    add_longshot_intrusion_features,
    paired_race_bootstrap_longshot_intrusion,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "race_id": ["R1"] * 4 + ["R2"] * 4,
        "finish_position": [4, 1, 5, 3, 2, 6, 1, 5],
        "win_odds": [8.0, 2.0, 12.0, 7.0, 9.0, 15.0, 2.5, 11.0],
        "market_implied_probability": [0.12, 0.45, 0.08, 0.15, 0.14, 0.07, 0.40, 0.09],
        "market_probability_rank": [3, 1, 4, 2, 2, 4, 1, 3],
        "horse_recent_top3_rate_5": [0.4, 0.8, 0.2, 0.5, 0.6, 0.2, 0.75, 0.35],
        "horse_recent_finish_percentile_mean_5": [0.45, 0.20, 0.65, 0.40, 0.35, 0.7, 0.22, 0.5],
        "horse_recent_early_ratio_mean_5": [0.55, 0.25, 0.70, 0.45, 0.38, 0.68, 0.30, 0.52],
        "horse_recent_late_ratio_mean_5": [0.45, 0.28, 0.66, 0.40, 0.42, 0.7, 0.33, 0.48],
        "jockey_past_win_rate": [0.10, 0.20, 0.06, 0.12, 0.13, 0.05, 0.19, 0.09],
        "jockey_course_past_win_rate": [0.09, 0.18, 0.05, 0.11, 0.12, 0.04, 0.17, 0.08],
        "horse_jockey_past_win_rate": [0.11, 0.24, 0.04, 0.13, 0.14, 0.03, 0.22, 0.07],
        "trainer_past_win_rate": [0.12, 0.18, 0.07, 0.10, 0.15, 0.06, 0.20, 0.08],
    })


def test_intrusion_features_compare_runner_to_market_leaders():
    frame = _frame()
    out, generated = add_longshot_intrusion_features(frame)

    assert "intrusion_market_rank_pct" in generated
    assert "intrusion_horse_recent_top3_rate_5_vs_favorite" in generated
    assert "intrusion_jockey_past_win_rate_vs_market_top3_mean" in generated

    favorite_r1 = out.loc[(out["race_id"] == "R1") & (out["market_probability_rank"] == 1)]
    assert np.isclose(
        favorite_r1["intrusion_horse_recent_top3_rate_5_vs_favorite"].iloc[0],
        0.0,
    )


def test_intrusion_features_do_not_depend_on_same_race_finish():
    original = _frame()
    changed = original.copy()
    changed["finish_position"] = [8, 7, 6, 5, 4, 3, 2, 1]

    original_out, generated = add_longshot_intrusion_features(original)
    changed_out, _ = add_longshot_intrusion_features(changed)

    pd.testing.assert_frame_equal(
        original_out[list(generated)],
        changed_out[list(generated)],
    )


def test_longshot_bootstrap_detects_probability_and_top_pick_improvement():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [2, 6, 3, 7],
        "win_odds": [8.0, 12.0, 9.0, 15.0],
    })
    specialist = pd.Series([0.70, 0.10, 0.65, 0.10], index=frame.index)
    baseline = pd.Series([0.45, 0.30, 0.40, 0.35], index=frame.index)

    evidence = paired_race_bootstrap_longshot_intrusion(
        frame,
        specialist,
        baseline,
        samples=100,
        seed=7,
    )

    assert evidence["binary_log_loss_improvement_support"] == 1.0
    assert evidence["brier_improvement_support"] == 1.0
    assert evidence["top_pick_hit_rate_improvement_support"] == 0.0


def test_phase7_protocol_preserves_holdout_and_forward_paper():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase7.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase7_request.txt"
    ).read_text(encoding="utf-8")

    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "top_pick_hit_rate_improvement_support" in source
    assert "2025-2026" in request
    assert "Forward Paper" in request
