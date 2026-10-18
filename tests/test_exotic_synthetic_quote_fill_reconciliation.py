"""Synthetic-only quote/fill ordering and fail-closed regressions."""
from decimal import Decimal
import pytest

from horse_racing_predictions.exotic_synthetic_quote_fill_reconciliation import (
    audit_synthetic_quote_fill_reconciliation,
)


def scenario(**updates):
    case = {
        "synthetic_only": True,
        "outcome": "filled",
        "observed_at": "2024-12-01T00:00:00Z",
        "captured_at": "2024-12-01T00:00:01Z",
        "decision_at": "2024-12-01T00:00:05Z",
        "fill_at": "2024-12-01T00:00:07Z",
        "purchase_cutoff_at": "2024-12-01T00:00:10Z",
        "scheduled_post_at": "2024-12-01T00:02:10Z",
        "displayed_decimal_odds": "10",
        "filled_decimal_odds": "9",
        "stake_yen": 100,
        "attempt_fee_yen": "1",
    }
    case.update(updates)
    return case


def test_filled_synthetic_quote_haircut_is_visible_but_no_ev_claim():
    x = audit_synthetic_quote_fill_reconciliation(scenario())
    assert x["outcome"] == "filled"
    assert x["attempted_stake_yen"] == x["filled_stake_yen"] == 100
    assert Decimal(x["hypothetical_price_slippage_multiple"]) == -1
    assert Decimal(x["hypothetical_relative_price_slippage"]) == Decimal("-0.1")
    assert x["real_fill_verified"] is False
    assert x["positive_executable_ev_proven"] is False
    assert x["paper_or_live_action_authorized"] is False


def test_unfilled_keeps_attempt_fee_and_no_fabricated_purchase_price():
    x = audit_synthetic_quote_fill_reconciliation(scenario(
        outcome="unfilled", fill_at=None, filled_decimal_odds=None,
    ))
    assert x["attempted_stake_yen"] == 100
    assert x["filled_stake_yen"] == 0
    assert x["paid_attempt_fee_yen"] == "1"
    assert x["hypothetical_filled_odds"] is None
    assert x["hypothetical_relative_price_slippage"] is None


@pytest.mark.parametrize("change", [
    {"synthetic_only": False},
    {"outcome": "live"},
    {"observed_at": "2024-12-01T00:00:06Z"},
    {"captured_at": "2024-12-01T00:00:06Z"},
    {"decision_at": "2024-12-01T00:00:11Z"},
    {"fill_at": "2024-12-01T00:00:12Z"},
    {"fill_at": "2024-12-01T00:00:03Z"},
    {"purchase_cutoff_at": "2024-12-01T00:02:10Z"},
    {"scheduled_post_at": "2024-12-01T00:00:10Z"},
    {"filled_decimal_odds": "1"},
    {"filled_decimal_odds": "NaN"},
    {"displayed_decimal_odds": "inf"},
    {"stake_yen": 101},
    {"stake_yen": True},
    {"attempt_fee_yen": "-1"},
    {"attempt_fee_yen": 0},
    {"outcome": "unfilled", "fill_at": None},
    {"outcome": "unfilled", "filled_decimal_odds": None},
    {"final_payout": "1000"},
    {"observed_at": "2025-01-01T00:00:01"},
])
def test_invalid_synthetic_timeline_fails_closed(change):
    with pytest.raises(ValueError):
        audit_synthetic_quote_fill_reconciliation(scenario(**change))
