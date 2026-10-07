from pathlib import Path

import pandas as pd

from horse_racing_predictions.exotic_longshot_phase8 import (
    _ranking_evidence,
    paired_race_bootstrap_longshot_ranking,
)


def test_ranking_evidence_rewards_better_longshot_ordering():
    frame = pd.DataFrame({
        "race_id": ["R1", "R1", "R2", "R2"],
        "finish_position": [2, 6, 3, 7],
    })
    specialist = pd.Series(
        [0.8, 0.2, 0.7, 0.3],
        index=frame.index,
    )
    baseline = pd.Series(
        [0.3, 0.7, 0.4, 0.6],
        index=frame.index,
    )

    evidence = _ranking_evidence(
        frame,
        specialist,
        baseline,
    )

    assert evidence["specialist_top1_hit"].eq(1).all()
    assert evidence["baseline_top1_hit"].eq(0).all()
    assert evidence["specialist_mrr"].eq(1.0).all()
    assert evidence["baseline_mrr"].eq(0.5).all()


def test_longshot_ranking_bootstrap_detects_improvement():
    evidence = pd.DataFrame({
        "race_id": ["R1", "R2", "R3"],
        "specialist_top1_hit": [1, 1, 1],
        "baseline_top1_hit": [0, 0, 0],
        "specialist_mrr": [1.0, 1.0, 1.0],
        "baseline_mrr": [0.5, 0.5, 0.5],
    })
    result = paired_race_bootstrap_longshot_ranking(
        evidence,
        samples=100,
        seed=8,
    )
    assert result["top1_hit_rate_improvement_support"] == 1.0
    assert result["mrr_improvement_support"] == 1.0


def test_phase8_protocol_keeps_general_probability_source_and_holdout():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase8.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase8_request.txt"
    ).read_text(encoding="utf-8")

    assert "not used as calibrated probability" in source
    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "Phase 7" in request
    assert "ranking-only" in request
    assert "2025-2026" in request
