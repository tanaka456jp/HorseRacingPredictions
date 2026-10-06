from pathlib import Path

import pandas as pd

from horse_racing_predictions.exotic_trio_phase6 import (
    DIRECT_TRIO_MAX_NEGATIVES_PER_RACE,
    build_direct_trio_candidates,
)


def _frame():
    rows=[]
    for race_id in ("R1","R2"):
        for i in range(5):
            rows.append({
                "race_id": race_id,
                "finish_position": i+1,
                "win_odds": [2.0,4.0,8.0,12.0,20.0][i],
                "market_implied_probability": [0.4,0.25,0.15,0.12,0.08][i],
                "market_probability_rank": float(i+1),
                "market_gap_to_favorite": 0.4-[0.4,0.25,0.15,0.12,0.08][i],
                "relative_post_position": i/4,
                "horse_recent_top3_rate_5": [0.8,0.6,0.5,0.3,0.2][i],
                "jockey_past_win_rate": [0.2,0.18,0.12,0.08,0.05][i],
                "trainer_past_win_rate": [0.18,0.16,0.10,0.07,0.04][i],
                "horse_jockey_past_win_rate": [0.25,0.2,0.1,0.05,0.02][i],
            })
    return pd.DataFrame(rows)


def test_direct_trio_candidates_have_one_positive_per_race():
    frame=_frame()
    candidates, features=build_direct_trio_candidates(frame,training=True)
    assert candidates.groupby("race_id")["is_actual_top3_set"].sum().eq(1).all()
    assert features
    assert candidates["set_longshot_count"].ge(0).all()


def test_direct_trio_eval_enumerates_all_sets():
    frame=_frame()
    candidates,_=build_direct_trio_candidates(frame,training=False)
    assert len(candidates)==20
    assert candidates.groupby("race_id").size().eq(10).all()


def test_phase6_protocol_preserves_holdout_and_forward_paper():
    source=Path("src/horse_racing_predictions/exotic_trio_phase6.py").read_text(encoding="utf-8")
    request=Path("research/exotic_direct_trio_phase6_request.txt").read_text(encoding="utf-8")
    assert '"2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "Phase 5 exact-three" in source
    assert "2025-2026" in request
    assert "Forward Paper" in request


def test_negative_cap_is_fixed():
    assert DIRECT_TRIO_MAX_NEGATIVES_PER_RACE == 31
