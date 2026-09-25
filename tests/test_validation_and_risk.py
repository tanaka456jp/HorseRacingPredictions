import pandas as pd

from horse_racing_predictions.backtest import simulate_win_strategy
from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.validation import (
    FINAL_WIN_ODDS,
    PRE_RACE_SNAPSHOT,
    classify_odds_evidence,
)

def _row(horse_id, horse_name, probability, odds, finish):
    return {
        "race_id": "R1",
        "race_date": "2026-01-01",
        "horse_id": horse_id,
        "horse_name": horse_name,
        "predicted_win_probability": probability,
        "decimal_odds": odds,
        "confidence": 1.0,
        "finish_position": finish,
        "model_version": "v0",
    }

def test_final_odds_roi_is_not_marked_verified():
    evidence = classify_odds_evidence(FINAL_WIN_ODDS)
    assert not evidence.roi_verified
    verified = classify_odds_evidence(PRE_RACE_SNAPSHOT)
    assert verified.roi_verified

def test_race_budget_is_shared_and_settled_after_race():
    frame = pd.DataFrame([
        _row("H1", "Alpha", 0.30, 5.0, 1),
        _row("H2", "Bravo", 0.25, 6.0, 2),
    ])
    detail, summary = simulate_win_strategy(
        frame,
        starting_bankroll_yen=100_000,
        config=StrategyConfig(
            min_ev=1.10,
            min_confidence=0.0,
            max_race_fraction=0.02,
            max_day_fraction=0.08,
        ),
    )

    assert detail["stake_yen"].sum() <= 2_000
    assert summary.stake_yen <= 2_000
    assert detail["bankroll_after_yen"].nunique() == 1

def test_day_budget_caps_multiple_races():
    rows = []
    for race_no in range(1, 6):
        rows.append({
            "race_id": f"R{race_no}",
            "race_date": "2026-01-01",
            "horse_id": f"H{race_no}",
            "horse_name": f"Horse {race_no}",
            "predicted_win_probability": 0.30,
            "decimal_odds": 5.0,
            "confidence": 1.0,
            "finish_position": 2,
            "model_version": "v0",
        })

    _, summary = simulate_win_strategy(
        pd.DataFrame(rows),
        starting_bankroll_yen=100_000,
        config=StrategyConfig(
            min_ev=1.10,
            min_confidence=0.0,
            max_race_fraction=0.02,
            max_day_fraction=0.05,
        ),
    )
    assert summary.stake_yen <= 5_000
