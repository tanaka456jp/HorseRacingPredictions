"""Synthetic-only regression checks for pre-decision exotic quote evidence.

No network, historic CSV, race results, staking, or holdout access.
A passing validation never grants source rights or executable-price approval.
"""
import pytest

from horse_racing_predictions.exotic_prebet_odds_contract import (
    inspect_exotic_prebet_quote,
)

DECISION = "2024-12-31T14:02:00+09:00"


def synthetic_quote(**overrides):
    quote = {
        "race_id": "SYNTHETIC-RACE",
        "bet_type": "trio",
        "horse_numbers": [9, 2, 5],
        "decimal_odds": "31.2",
        "source_name": "SYNTHETIC-NOT-REAL",
        "source_reference": "synthetic-fixture",
        "quote_stage": "pre_race",
        "odds_kind": "decimal_quote",
        "observed_at": "2024-12-31T14:01:00+09:00",
        "captured_at": "2024-12-31T14:01:02+09:00",
        "scheduled_post_time": "2024-12-31T14:05:00+09:00",
    }
    quote.update(overrides)
    return quote


def inspect(quote, *, decision_at=DECISION):
    result = inspect_exotic_prebet_quote(quote, decision_at=decision_at)
    assert result["approved_for_ev"] is False
    assert result["approved_for_acquisition"] is False
    return result


def test_trio_is_unordered_and_never_automatically_approved():
    first = inspect(synthetic_quote())
    second = inspect(synthetic_quote(horse_numbers=[5, 9, 2]))
    assert first["canonical_combination_key"] == second["canonical_combination_key"]
    assert first["status"] == "human_review_required"


def test_trifecta_is_ordered_and_never_automatically_approved():
    first = inspect(synthetic_quote(bet_type="trifecta"))
    second = inspect(synthetic_quote(bet_type="trifecta", horse_numbers=[5, 9, 2]))
    assert first["canonical_combination_key"] != second["canonical_combination_key"]
    assert first["status"] == "human_review_required"


@pytest.mark.parametrize("numbers", [
    [1, 1, 2], [0, 2, 3], [1, 2, 19], [True, 2, 3],
    [1.0, 2, 3], ["1", 2, 3], [1, 2], [1, 2, 3, 4], None,
])
def test_invalid_combination_fails_closed(numbers):
    assert inspect(synthetic_quote(horse_numbers=numbers))["status"] == "blocked"


@pytest.mark.parametrize("odds", [
    "1", "0", "-2", "NaN", "Infinity", "bad", None,
])
def test_invalid_odds_fail_closed(odds):
    assert inspect(synthetic_quote(decimal_odds=odds))["status"] == "blocked"


@pytest.mark.parametrize("field,value", [
    ("observed_at", "2024-12-31T14:01:03+09:00"),
    ("captured_at", "2024-12-31T14:02:01+09:00"),
    ("observed_at", "2024-12-31T14:01:00"),
    ("scheduled_post_time", "2024-12-31T14:02:00+09:00"),
])
def test_invalid_temporal_evidence_fails_closed(field, value):
    assert inspect(synthetic_quote(**{field: value}))["status"] == "blocked"


@pytest.mark.parametrize("field", [
    "payout", "final_payout", "settlement", "result",
    "finish_position", "final_odds",
])
def test_result_or_final_odds_fields_forbidden_even_when_empty(field):
    assert inspect(synthetic_quote(**{field: None}))["status"] == "blocked"


@pytest.mark.parametrize("field,value", [
    ("race_id", ""), ("source_name", " "), ("source_reference", None),
    ("quote_stage", "final"), ("odds_kind", "payout"), ("bet_type", "win"),
])
def test_missing_evidence_and_wrong_market_type_fail_closed(field, value):
    assert inspect(synthetic_quote(**{field: value}))["status"] == "blocked"


def test_non_object_fails_closed():
    assert inspect(None)["status"] == "blocked"


def test_timezone_offsets_are_normalized_for_review_only():
    quote = synthetic_quote(
        observed_at="2024-12-31T05:01:00Z",
        captured_at="2024-12-31T05:01:02+00:00",
    )
    result = inspect(quote, decision_at="2024-12-31T05:02:00Z")
    assert result["status"] == "human_review_required"


@pytest.mark.parametrize("unknown_field", [
    "winning_combination", "dividend", "final_return", "finish_order",
    "metadata", "result_payload", "post_race_status", "settlement_amount",
    "odds_after_post", "race_result", "payout_yen", "untrusted_extra",
])
def test_unknown_quote_fields_fail_closed(unknown_field):
    result = inspect(synthetic_quote(**{unknown_field: {"untrusted": True}}))
    assert result["status"] == "blocked"
    assert result["canonical_combination_key"] is None


def test_allowlisted_quote_remains_human_review_only():
    result = inspect(synthetic_quote())
    assert result["status"] == "human_review_required"
    assert result["blockers"] == []
    assert result["canonical_combination_key"] == "SYNTHETIC-RACE:trio:2-5-9"
