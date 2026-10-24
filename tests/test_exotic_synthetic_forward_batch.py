"""Fail-closed synthetic batch chronology, abstentions and budget."""
from decimal import Decimal
import pytest

from horse_racing_predictions.exotic_synthetic_forward_batch import (
    audit_synthetic_forward_batch,
)


def row(ticket="T1", race="S1", **updates):
    record = {
        "race_id": race, "candidate_id": ticket, "selection_status": "attempted",
        "observed_at": "2024-12-01T00:00:01Z",
        "decision_at": "2024-12-01T00:00:02Z",
        "purchase_cutoff_at": "2024-12-01T00:00:10Z",
        "scheduled_post_at": "2024-12-01T00:02:00Z",
        "stake_yen": 100, "hypothetical_fill_fraction": "0.01",
    }
    record.update(updates)
    return record


def case(rows=None, **updates):
    value = {
        "synthetic_only": True,
        "model_finalized_at": "2024-11-30T23:59:59Z",
        "max_race_stake_yen": 200,
        "max_day_stake_yen": 300,
        "opportunities": (
            [row("T1", "S1"), row("T2", "S1"), row(
                "T3", "S2", selection_status="abstained",
                observed_at=None, stake_yen=0,
                hypothetical_fill_fraction=None,
            )] if rows is None else rows
        ),
    }
    value.update(updates)
    return value


def test_full_stake_reservation_does_not_use_one_percent_fill():
    x = audit_synthetic_forward_batch(case())
    assert x["worst_case_all_fill_reserved_yen"] == 200
    assert Decimal(x["hypothetical_expected_fill_stake_yen"]) == 2
    assert x["eligible_opportunity_count"] == 3
    assert x["attempted_count"] == 2
    assert x["abstained_count"] == 1
    assert x["positive_executable_ev_proven"] is False
    assert x["paper_or_live_action_authorized"] is False


def test_oversubscribed_same_race_even_if_all_fills_zero():
    with pytest.raises(ValueError, match="reservation cap"):
        audit_synthetic_forward_batch(case([
            row("T1", "S1", hypothetical_fill_fraction="0"),
            row("T2", "S1", hypothetical_fill_fraction="0"),
            row("T3", "S1", hypothetical_fill_fraction="0"),
        ]))


def test_cross_race_over_day_cap_rejected():
    with pytest.raises(ValueError, match="reservation cap"):
        audit_synthetic_forward_batch(case([
            row("T1", "S1"), row("T2", "S1"),
            row("T3", "S2"), row("T4", "S2"),
        ]))


@pytest.mark.parametrize("changed", [
    {"synthetic_only": False},
    {"max_race_stake_yen": 0},
    {"max_day_stake_yen": 150},
    {"model_finalized_at": "2025-01-01T00:00:00Z"},
    {"opportunities": []},
    {"allow_live": True},
])
def test_bad_batch_envelope_fails_closed(changed):
    with pytest.raises(ValueError):
        audit_synthetic_forward_batch(case(**changed))


@pytest.mark.parametrize("changed", [
    {"observed_at": "2024-11-30T23:59:58Z"},
    {"observed_at": "2024-12-01T00:00:03Z"},
    {"purchase_cutoff_at": "2024-12-01T00:02:00Z"},
    {"scheduled_post_at": "2025-01-01T00:00:00Z"},
    {"decision_at": "2025-01-01T00:00:00Z"},
    {"stake_yen": 101},
    {"hypothetical_fill_fraction": "1.01"},
    {"hypothetical_fill_fraction": 0.1},
    {"selection_status": "live_bet"},
    {"selection_status": "abstained", "stake_yen": 0},
    {"selection_status": "abstained", "observed_at": None},
    {"selection_status": "abstained", "hypothetical_fill_fraction": None},
    {"final_payout": "100"},
    {"race_id": "2024120101"},
])
def test_invalid_quotes_and_abstention_fail_closed(changed):
    with pytest.raises(ValueError):
        audit_synthetic_forward_batch(case([row(**changed)]))


def test_duplicate_ticket_and_cross_day_scenarios_fail_closed():
    with pytest.raises(ValueError, match="duplicate"):
        audit_synthetic_forward_batch(case([
            row("T1", "S1"), row("T1", "S2"),
        ]))
    with pytest.raises(ValueError, match="one synthetic UTC decision day"):
        audit_synthetic_forward_batch(case([
            row("T1", "S1"),
            row("T2", "S2", decision_at="2024-12-02T00:00:02Z",
                purchase_cutoff_at="2024-12-02T00:00:10Z",
                scheduled_post_at="2024-12-02T00:02:00Z",
                observed_at="2024-12-02T00:00:01Z"),
        ]))
