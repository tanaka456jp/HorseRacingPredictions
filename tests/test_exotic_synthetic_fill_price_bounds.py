"""Synthetic-only break-even regression; never grants trading permission."""
from decimal import Decimal

import pytest

from horse_racing_predictions.exotic_synthetic_fill_price_bounds import (
    audit_synthetic_fill_price_bounds,
)


def scenario(**changes):
    case = {
        "synthetic_only": True,
        "conditional_win_probability_lower": "0.15",
        "displayed_decimal_odds": "10",
        "payout_haircut": "0.20",
        "fill_fraction": "0.5",
        "stake_yen": 100,
        "fee_per_fill_yen": "10",
        "fee_per_attempt_yen": "5",
        "max_race_stake_yen": 100,
        "max_day_stake_yen": 100,
    }
    case.update(changes)
    return case


def test_break_even_reconciles_with_net_ev():
    result = audit_synthetic_fill_price_bounds(scenario())
    assert Decimal(result["break_even_conditional_probability_under_assumptions"]) == Decimal("0.15")
    assert Decimal(result["net_ev_yen_per_attempt"]) == 0
    assert result["break_even_attainable_under_assumptions"] is True


@pytest.mark.parametrize("probability,sign", [("0.14", -1), ("0.16", 1)])
def test_synthetic_ev_sign_around_break_even(probability, sign):
    result = audit_synthetic_fill_price_bounds(scenario(conditional_win_probability_lower=probability))
    assert Decimal(result["net_ev_yen_per_attempt"]) * sign > 0
    assert result["positive_executable_ev_proven"] is False
    assert result["paper_or_live_action_authorized"] is False


def test_zero_fill_break_even_undefined_and_attempt_cost_retained():
    result = audit_synthetic_fill_price_bounds(scenario(fill_fraction="0"))
    assert result["break_even_conditional_probability_under_assumptions"] is None
    assert result["break_even_attainable_under_assumptions"] is False
    assert Decimal(result["net_ev_yen_per_attempt"]) == -5


def test_unattainable_threshold_is_explicit():
    result = audit_synthetic_fill_price_bounds(scenario(
        displayed_decimal_odds="2", payout_haircut="0.90",
        fee_per_fill_yen="0", fee_per_attempt_yen="0",
    ))
    assert Decimal(result["break_even_conditional_probability_under_assumptions"]) == 5
    assert result["break_even_attainable_under_assumptions"] is False


def test_daily_cap_and_opportunity_coverage_are_not_claimed():
    result = audit_synthetic_fill_price_bounds(scenario())
    assert result["daily_aggregate_cap_verified"] is False
    assert result["eligible_opportunity_coverage_verified"] is False
    assert result["quote_rights_verified"] is False
    assert result["purchase_price_verified"] is False


def test_increasing_attempt_fee_raises_break_even():
    low = audit_synthetic_fill_price_bounds(scenario(fee_per_attempt_yen="0"))
    high = audit_synthetic_fill_price_bounds(scenario(fee_per_attempt_yen="10"))
    key = "break_even_conditional_probability_under_assumptions"
    assert Decimal(high[key]) > Decimal(low[key])


def test_noncanonical_input_and_unauthorized_flags_rejected():
    with pytest.raises(ValueError):
        audit_synthetic_fill_price_bounds(scenario(fill_fraction=0.5))
    with pytest.raises(ValueError):
        audit_synthetic_fill_price_bounds(scenario(quote_rights_verified=True))
