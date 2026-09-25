import pandas as pd

from horse_racing_predictions.strategy_selection import (
    forward_select_ev_threshold,
    summarize_forward_selection,
)


def _row(fold, p, odds, finish):
    return {
        "fold_number": fold,
        "predicted_win_probability": p,
        "decimal_odds": odds,
        "finish_position": finish,
    }


def test_forward_selector_never_uses_target_fold_for_rule_choice():
    rows = []
    for fold in (1, 2, 3):
        rows += [
            _row(fold, 0.25, 5.0, 1),
            _row(fold, 0.20, 5.5, 2),
        ]

    rows += [
        _row(4, 0.25, 5.0, 2),
        _row(4, 0.20, 5.5, 1),
    ]

    selected, decisions = forward_select_ev_threshold(
        pd.DataFrame(rows),
        candidate_thresholds=(1.05, 1.20),
        min_history_folds=3,
        min_prior_bets=3,
    )

    assert len(decisions) == 1
    assert decisions[0].target_fold == 4
    assert decisions[0].selected_min_ev == 1.20
    assert selected.loc[0, "selected_min_ev"] == 1.20


def test_selector_abstains_when_prior_rules_are_negative():
    rows = []
    for fold in (1, 2, 3, 4):
        rows += [
            _row(fold, 0.25, 5.0, 2),
            _row(fold, 0.20, 6.0, 2),
        ]

    selected, decisions = forward_select_ev_threshold(
        pd.DataFrame(rows),
        candidate_thresholds=(1.05, 1.20),
        min_history_folds=3,
        min_prior_bets=3,
        require_positive_prior_roi=True,
    )

    assert decisions[0].selected_min_ev is None
    assert not selected["strategy_selected"].any()

    summary = summarize_forward_selection(selected)
    assert summary["bets"] == 0
    assert summary["abstain_rate"] == 1.0
