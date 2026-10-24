"""Synthetic-only opportunity accounting, no real race or payout intake."""
from decimal import Decimal
import pytest

from horse_racing_predictions.exotic_synthetic_forward_settlement import (
    audit_synthetic_forward_settlement,
)


def row(id="T1", race="S1", **change):
    value = {
        "attempt_id": id,
        "race_id": race,
        "observed_at": "2024-12-01T00:00:00Z",
        "decision_at": "2024-12-01T00:00:05Z",
        "purchase_at": "2024-12-01T00:00:06Z",
        "purchase_cutoff_at": "2024-12-01T00:00:10Z",
        "scheduled_post_at": "2024-12-01T00:02:00Z",
        "settled_at": "2024-12-01T00:04:00Z",
        "status": "filled",
        "stake_yen": 100,
        "pre_purchase_decimal_odds": "20",
        "hypothetical_settlement_multiplier": "2",
        "fee_yen": "1",
    }
    value.update(change)
    return value


def case(rows=None, **change):
    value = {
        "synthetic_only": True,
        "max_race_stake_yen": 200,
        "max_day_stake_yen": 300,
        "opportunities": [row()] if rows is None else rows,
    }
    value.update(change)
    return value


def test_filled_and_unfilled_settlement_are_separate():
    entries = [
        row("T1", "S1"),
        row("T2", "S1", status="unfilled", purchase_at=None,
            settled_at=None, hypothetical_settlement_multiplier=None,
            fee_yen="2"),
        row("T3", "S2", hypothetical_settlement_multiplier="0",
            fee_yen="3"),
    ]
    result = audit_synthetic_forward_settlement(case(entries))
    assert result["opportunities"] == 3
    assert result["filled_attempts"] == 2
    assert result["unfilled_attempts"] == 1
    assert result["all_fill_reserved_yen"] == 300
    assert result["hypothetical_filled_stake_yen"] == 200
    # +99 -2 -103 == -6
    assert Decimal(result["hypothetical_net_profit_yen"]) == -6
    assert Decimal(result["hypothetical_filled_stake_roi"]) == Decimal("-0.03")
    assert Decimal(result["chronological_max_drawdown_yen"]) >= 0
    assert result["outcome_stage_separated_from_quote_stage"]
    assert result["positive_executable_ev_proven"] is False
    assert result["real_settlement_verified"] is False


def test_only_unfilled_still_pays_attempt_fee_with_no_roi():
    result = audit_synthetic_forward_settlement(case([
        row(status="unfilled", purchase_at=None, settled_at=None,
            hypothetical_settlement_multiplier=None),
    ]))
    assert Decimal(result["hypothetical_net_profit_yen"]) == -1
    assert result["hypothetical_filled_stake_roi"] is None
    assert result["hypothetical_filled_stake_yen"] == 0


@pytest.mark.parametrize("change", [
    {"synthetic_only": False},
    {"max_race_stake_yen": True},
    {"max_day_stake_yen": 150},
    {"max_race_stake_yen": 400},
    {"opportunities": []},
    {"result": "profit"},
])
def test_invalid_envelope_rejected(change):
    with pytest.raises(ValueError):
        audit_synthetic_forward_settlement(case(**change))


@pytest.mark.parametrize("bad", [
    {"purchase_at": "2024-12-01T00:00:11Z"},
    {"settled_at": "2024-12-01T00:01:00Z"},
    {"observed_at": "2024-12-01T00:00:07Z"},
    {"purchase_cutoff_at": "2024-12-01T00:02:01Z"},
    {"settled_at": "2025-01-01T00:00:00Z"},
    {"status": "win"},
    {"pre_purchase_decimal_odds": "1"},
    {"pre_purchase_decimal_odds": "NaN"},
    {"hypothetical_settlement_multiplier": "-1"},
    {"stake_yen": 101},
    {"fee_yen": 1},
    {"outcome_from_future": 1},
    {"status": "unfilled", "purchase_at": None},
    {"status": "unfilled", "settled_at": None},
    {"status": "unfilled", "hypothetical_settlement_multiplier": None},
])
def test_invalid_outcome_or_timeline_fails_closed(bad):
    with pytest.raises(ValueError):
        audit_synthetic_forward_settlement(case([row(**bad)]))


def test_duplicate_ticket_and_all_fill_limits_block_entire_ledger():
    with pytest.raises(ValueError, match="duplicate"):
        audit_synthetic_forward_settlement(case([row("T1"), row("T1", "S2")]))
    with pytest.raises(ValueError, match="capital cap"):
        audit_synthetic_forward_settlement(case([
            row("T1", "S1"), row("T2", "S1"), row("T3", "S1")
        ]))
    with pytest.raises(ValueError, match="capital cap"):
        audit_synthetic_forward_settlement(case([
            row("T1", "S1"), row("T2", "S1"),
            row("T3", "S2"), row("T4", "S2")
        ]))
