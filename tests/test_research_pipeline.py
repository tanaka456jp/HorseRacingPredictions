import pandas as pd
import pytest

from horse_racing_predictions.backtest import simulate_win_strategy
from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.data_sources import normalize_jra_history
from horse_racing_predictions.leakage import audit_model_features, assert_leakage_safe

def test_jra_history_normalization():
    raw = pd.DataFrame({
        "レースID": ["202601010101"],
        "レース日付": ["2026-01-01"],
        "競馬場名": ["京都"],
        "芝・ダート区分": ["芝"],
        "距離(m)": [1600],
        "着順": [1],
        "馬番": [3],
        "馬名": ["TEST HORSE"],
        "単勝": [6.0],
        "馬体重": [480],
        "騎手": ["TEST JOCKEY"],
    })
    out = normalize_jra_history(raw)
    assert out.loc[0, "race_id"] == "202601010101"
    assert out.loc[0, "distance_m"] == 1600
    assert out.loc[0, "win_odds"] == 6.0
    assert out.loc[0, "finish_position"] == 1

def test_leakage_audit_blocks_current_race_results_and_unsnapped_odds():
    result = audit_model_features(
        ["distance_m", "past_last_3f", "finish_position", "win_odds"]
    )
    assert not result.safe
    assert result.forbidden == ("finish_position",)
    assert result.asof_required == ("win_odds",)
    with pytest.raises(ValueError):
        assert_leakage_safe(["distance_m", "finish_position"])

def test_backtest_buys_only_positive_ev_candidate():
    frame = pd.DataFrame([
        {
            "race_id": "R1", "horse_id": "H1", "horse_name": "Alpha",
            "predicted_win_probability": 0.25, "decimal_odds": 6.0,
            "confidence": 0.8, "finish_position": 1, "model_version": "v0",
        },
        {
            "race_id": "R2", "horse_id": "H2", "horse_name": "Bravo",
            "predicted_win_probability": 0.60, "decimal_odds": 1.5,
            "confidence": 0.8, "finish_position": 2, "model_version": "v0",
        },
    ])
    detail, summary = simulate_win_strategy(
        frame,
        starting_bankroll_yen=100_000,
        config=StrategyConfig(min_ev=1.15),
    )
    assert summary.bets == 1
    assert summary.profit_yen > 0
    assert summary.ending_bankroll_yen > 100_000
    assert detail.loc[1, "stake_yen"] == 0
