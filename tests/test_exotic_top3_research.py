from pathlib import Path

import numpy as np
import pandas as pd

from horse_racing_predictions.exotic_top3_research import (
    TOP3_LONGSHOT_ODDS_MIN,
    add_top3_race_interaction_features,
    paired_race_bootstrap_binary_quality,
    top3_outcomes,
)


def _interaction_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "race_id": ["R1", "R1", "R1", "R2", "R2", "R2"],
        "finish_position": [1, 5, 3, 4, 1, 2],
        "horse_recent_top3_rate_5": [0.8, 0.2, 0.5, 0.1, 0.7, 0.4],
        "horse_recent_early_ratio_mean_5": [
            0.2, 0.8, 0.5, 0.7, 0.3, 0.4
        ],
        "jockey_past_win_rate": [0.2, 0.1, 0.15, 0.08, 0.18, 0.12],
        "market_implied_probability": [
            0.50, 0.20, 0.30, 0.15, 0.55, 0.30
        ],
    })


def test_top3_outcomes_marks_first_three_places():
    frame = pd.DataFrame({
        "finish_position": [1, 2, 3, 4, 10],
    })
    assert top3_outcomes(frame).tolist() == [1, 1, 1, 0, 0]


def test_race_interaction_features_are_relative_within_race():
    frame = _interaction_frame()
    out, generated = add_top3_race_interaction_features(frame)

    assert "horse_recent_top3_rate_5_vs_race_mean" in generated
    assert "market_race_entropy" in generated
    assert "market_top3_probability_share" in generated

    r1 = out.loc[out["race_id"].eq("R1")]
    assert np.isclose(
        r1["horse_recent_top3_rate_5_vs_race_mean"].sum(),
        0.0,
    )
    assert np.isclose(
        r1["market_top3_probability_share"].iloc[0],
        1.0,
    )


def test_race_interaction_features_do_not_depend_on_same_race_finish():
    original = _interaction_frame()
    changed = original.copy()
    changed["finish_position"] = [6, 5, 4, 3, 2, 1]

    original_out, generated = add_top3_race_interaction_features(
        original
    )
    changed_out, _ = add_top3_race_interaction_features(
        changed
    )

    pd.testing.assert_frame_equal(
        original_out[list(generated)],
        changed_out[list(generated)],
    )


def test_phase1_protocol_preserves_holdout_and_excludes_pedigree_identifier():
    source = Path(
        "src/horse_racing_predictions/exotic_top3_research.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_top3_phase1_request.txt"
    ).read_text(encoding="utf-8")

    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "paid_data" in source
    assert "_jv_blood_registration_number" not in source
    assert "semantic sire/dam" in source
    assert "2025-2026" in request
    assert "Forward Paper" in request


def test_longshot_proxy_keeps_preregistered_six_odds_boundary():
    assert TOP3_LONGSHOT_ODDS_MIN == 6.0



def test_paired_race_bootstrap_detects_better_top3_challenger():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R1", "R2", "R2", "R2"],
        "finish_position": [1, 4, 5, 2, 6, 7],
    })
    challenger = pd.Series(
        [0.80, 0.10, 0.10, 0.75, 0.10, 0.10],
        index=frame.index,
        dtype=float,
    )
    baseline = pd.Series(
        [0.55, 0.25, 0.20, 0.50, 0.25, 0.20],
        index=frame.index,
        dtype=float,
    )

    evidence = paired_race_bootstrap_binary_quality(
        frame,
        challenger,
        baseline,
        samples=100,
        seed=123,
    )

    assert (
        evidence["binary_log_loss_improvement_support"]
        == 1.0
    )
    assert evidence["brier_improvement_support"] == 1.0


def test_paired_race_bootstrap_is_deterministic():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [1, 5, 2, 6],
    })
    challenger = pd.Series(
        [0.65, 0.20, 0.60, 0.20],
        index=frame.index,
        dtype=float,
    )
    baseline = pd.Series(
        [0.60, 0.25, 0.55, 0.25],
        index=frame.index,
        dtype=float,
    )

    first = paired_race_bootstrap_binary_quality(
        frame,
        challenger,
        baseline,
        samples=50,
        seed=7,
    )
    second = paired_race_bootstrap_binary_quality(
        frame,
        challenger,
        baseline,
        samples=50,
        seed=7,
    )

    assert first == second
