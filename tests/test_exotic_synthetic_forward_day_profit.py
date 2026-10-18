"""Synthetic-only same-race, day-cluster sensitivity and no-bet preservation."""
from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_synthetic_forward_day_profit import (
    audit_synthetic_forward_day_profit,
)


def race(id="S1", day="2023-05-05", **change):
    item = {
        "day": day, "race_id": id,
        "strategy_stake_yen": 100, "market_stake_yen": 100,
        "strategy_net_yen": "10", "market_net_yen": "-10",
    }
    item.update(change)
    return item


def case(rows=None, **change):
    item = {
        "synthetic_only": True,
        "strategy_frozen_before_evaluation": True,
        "benchmark_frozen_before_evaluation": True,
        "max_race_stake_yen": 200,
        "max_day_stake_yen": 200,
        "bootstrap_samples": 100,
        "bootstrap_seed": 20261017,
        "comparisons": [race()] if rows is None else rows,
    }
    item.update(change)
    return item


def test_day_bootstrap_is_clustered_and_returns_fictional_profit_not_ev():
    rows = [
        race("S1", "2023-05-05"),
        race("S2", "2024-05-05"),
    ]
    x = audit_synthetic_forward_day_profit(case(rows))
    assert x["synthetic_races"] == 2
    assert x["synthetic_days"] == 2
    assert Decimal(x["strategy_net_profit_yen"]) == 20
    assert Decimal(x["market_net_profit_yen"]) == -20
    assert Decimal(x["net_profit_delta_vs_market_yen"]) == 40
    assert Decimal(x["strategy_net_roi"]) == Decimal(".1")
    assert Decimal(x["market_net_roi"]) == Decimal("-.1")
    assert Decimal(x["exploratory_delta_q05_yen"]) == 40
    assert Decimal(x["exploratory_delta_q95_yen"]) == 40
    assert x["formal_confidence_interval"] is False
    assert x["positive_executable_ev_proven"] is False


def test_unbought_opportunities_remain_in_same_race_denominator():
    x = audit_synthetic_forward_day_profit(case([
        race("S1", strategy_stake_yen=0, strategy_net_yen="-2"),
        race("S2", market_stake_yen=0, market_net_yen="-3"),
    ]))
    assert x["synthetic_races"] == 2
    assert x["strategy_no_stake_opportunities"] == 1
    assert x["market_no_stake_opportunities"] == 1
    assert x["strategy_total_stake_yen"] == 100
    assert x["market_total_stake_yen"] == 100


def test_no_bet_all_has_undefined_roi_and_zero_profit():
    x = audit_synthetic_forward_day_profit(case([
        race(strategy_stake_yen=0, market_stake_yen=0,
             strategy_net_yen="0", market_net_yen="0"),
    ]))
    assert x["strategy_net_roi"] is None
    assert x["market_net_roi"] is None


@pytest.mark.parametrize("change", [
    {"synthetic_only": False},
    {"strategy_frozen_before_evaluation": False},
    {"benchmark_frozen_before_evaluation": False},
    {"max_day_stake_yen": 150},
    {"max_race_stake_yen": True},
    {"bootstrap_samples": 1},
    {"bootstrap_seed": -1},
    {"comparisons": []},
    {"final_payouts": []},
])
def test_bad_protocol_envelope_fails_closed(change):
    with pytest.raises(ValueError):
        audit_synthetic_forward_day_profit(case(**change))


@pytest.mark.parametrize("bad", [
    {"day": "2025-01-01"},
    {"day": "2023-02-30"},
    {"day": "2023/05/05"},
    {"race_id": "2023050501"},
    {"strategy_stake_yen": 101},
    {"market_stake_yen": 300},
    {"strategy_net_yen": "NaN"},
    {"strategy_net_yen": 10},
    {"market_net_yen": "inf"},
    {"strategy_stake_yen": 0, "strategy_net_yen": "1"},
    {"market_stake_yen": 0, "market_net_yen": "1"},
    {"actual_race_result": 1},
])
def test_invalid_race_entries_rejected(bad):
    with pytest.raises(ValueError):
        audit_synthetic_forward_day_profit(case([race(**bad)]))


def test_cumulative_same_day_cap_and_duplicate_race_guarded():
    with pytest.raises(ValueError, match="day capital cap"):
        audit_synthetic_forward_day_profit(case([
            race("S1"), race("S2"), race("S3"),
        ]))
    with pytest.raises(ValueError, match="distinct synthetic race"):
        audit_synthetic_forward_day_profit(case([
            race("S1"), race("S1", "2024-01-01"),
        ]))


def test_positive_relative_delta_is_not_proof_of_profit():
    x = audit_synthetic_forward_day_profit(case([
        race(strategy_net_yen="-90", market_net_yen="-100"),
    ]))
    assert Decimal(x["net_profit_delta_vs_market_yen"]) == 10
    assert Decimal(x["strategy_net_profit_yen"]) < 0
    assert x["positive_executable_ev_proven"] is False
