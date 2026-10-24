"""Synthetic-only monotonically adverse stress grid, full race denominator."""
from decimal import Decimal
import pytest

from horse_racing_predictions.exotic_synthetic_stress_grid import (
    audit_synthetic_stress_grid,
)


def race(id="S1", **updates):
    item = {
        "race_id": id, "strategy_status": "filled",
        "strategy_stake_yen": 100, "attempt_fee_yen": "1",
        "hypothetical_settlement_multiplier": "3",
        "frozen_market_net_yen": "-10",
    }
    item.update(updates)
    return item


def case(rows=None, **updates):
    value = {
        "synthetic_only": True,
        "protocol_frozen_before_evaluation": True,
        "max_day_stake_yen": 300,
        "payout_haircuts": ["0", "0.10", "0.50"],
        "adverse_nonfill_counts": [0, 1, 2],
        "races": ([race("S1"), race("S2"),
                   race("S3", strategy_status="abstained",
                        strategy_stake_yen=0, attempt_fee_yen="0",
                        hypothetical_settlement_multiplier=None)]
                  if rows is None else rows),
    }
    value.update(updates)
    return value


def test_grid_stress_never_improves_profit_or_fabricates_executable_ev():
    x = audit_synthetic_stress_grid(case())
    assert x["eligible_synthetic_races"] == 3
    assert x["attempted_worst_case_stake_yen"] == 200
    assert len(x["cells"]) == 9
    by_haircut = {}
    for cell in x["cells"]:
        by_haircut.setdefault(cell["payout_haircut"], []).append(
            Decimal(cell["fictional_strategy_net_yen"])
        )
        assert cell["frozen_market_net_yen"] == "-30"
    for profits in by_haircut.values():
        assert profits == sorted(profits, reverse=True)
    for col in range(3):
        assert [v[col] for v in by_haircut.values()] == sorted(
            [v[col] for v in by_haircut.values()], reverse=True,
        )
    assert x["ex_post_adverse_nonfills_not_prospective_model"]
    assert x["formal_confidence_interval"] is False
    assert x["positive_executable_ev_proven"] is False
    assert x["paper_or_live_action_authorized"] is False


def test_abstained_and_unfilled_still_count_as_opportunities():
    x = audit_synthetic_stress_grid(case([
        race("S1", strategy_status="unfilled", hypothetical_settlement_multiplier=None),
        race("S2", strategy_status="abstained", strategy_stake_yen=0,
             hypothetical_settlement_multiplier=None, attempt_fee_yen="0"),
    ], adverse_nonfill_counts=[0, 1]))
    assert x["eligible_synthetic_races"] == 2
    assert Decimal(x["cells"][0]["fictional_strategy_net_yen"]) == -1
    assert Decimal(x["cells"][1]["fictional_strategy_net_yen"]) == -1


@pytest.mark.parametrize("updates", [
    {"synthetic_only": False},
    {"protocol_frozen_before_evaluation": False},
    {"payout_haircuts": ["0.10"]},
    {"payout_haircuts": ["0", "0", "0.10"]},
    {"payout_haircuts": ["0", "0.96"]},
    {"payout_haircuts": ["0", "NaN"]},
    {"adverse_nonfill_counts": [1]},
    {"adverse_nonfill_counts": [0, 0]},
    {"adverse_nonfill_counts": [0, True]},
    {"adverse_nonfill_counts": [0, 4]},
    {"max_day_stake_yen": 100},
    {"max_day_stake_yen": True},
    {"races": []},
    {"approved_for_live": True},
])
def test_stress_envelope_invalid_data_fails_closed(updates):
    with pytest.raises(ValueError):
        audit_synthetic_stress_grid(case(**updates))


@pytest.mark.parametrize("updates", [
    {"strategy_status": "abstained"},
    {"strategy_status": "unfilled"},
    {"strategy_stake_yen": 101},
    {"attempt_fee_yen": "-1"},
    {"hypothetical_settlement_multiplier": "-1"},
    {"frozen_market_net_yen": "NaN"},
    {"source_data": "real"},
    {"race_id": "2023100101"},
])
def test_invalid_race_entry_rejected(updates):
    with pytest.raises(ValueError):
        audit_synthetic_stress_grid(case([race(**updates)]))


def test_duplicate_race_cannot_mask_inconsistent_market_baseline():
    with pytest.raises(ValueError, match="unique"):
        audit_synthetic_stress_grid(case([
            race("S1"), race("S1", frozen_market_net_yen="1000"),
        ]))
