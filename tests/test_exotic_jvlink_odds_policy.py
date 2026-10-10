from datetime import date

import pytest

from horse_racing_predictions.exotic_jvlink_odds_policy import (
    classify_jv_odds_evidence,
)


@pytest.mark.parametrize(
    "code,bet_type",
    [
        ("O5", "trio"),
        ("o5", "trio"),
        ("O6", "trifecta"),
    ],
)
def test_setup_exotic_odds_are_final_and_never_prebet_ev(code, bet_type):
    policy = classify_jv_odds_evidence(code)
    assert policy.bet_type == bet_type
    assert policy.evidence_kind == "final_odds"
    assert policy.can_be_prebet_quote is False
    assert policy.can_be_strict_ev_input is False
    assert "final odds" in policy.reason


@pytest.mark.parametrize("code", ["0B41", "0B42"])
def test_jv_time_series_dataspecs_do_not_cover_trio_or_trifecta(code):
    policy = classify_jv_odds_evidence(code)
    assert policy.bet_type is None
    assert policy.evidence_kind == "historical_time_series_non_exotic"
    assert policy.can_be_prebet_quote is False
    assert policy.can_be_strict_ev_input is False


@pytest.mark.parametrize(
    "code,bet_type",
    [
        ("0B35", "trio"),
        ("0B36", "trifecta"),
    ],
)
def test_realtime_exotic_can_only_be_candidate_evidence_outside_holdout(
    code,
    bet_type,
):
    policy = classify_jv_odds_evidence(
        code,
        race_date=date(2027, 1, 5),
    )
    assert policy.bet_type == bet_type
    assert policy.evidence_kind == "realtime_exotic_snapshot"
    assert policy.can_be_prebet_quote is True
    assert policy.can_be_strict_ev_input is False
    assert policy.protected_holdout_blocked is False


@pytest.mark.parametrize(
    "race_date",
    [
        date(2025, 1, 1),
        date(2025, 12, 31),
        date(2026, 1, 1),
        date(2026, 12, 31),
    ],
)
@pytest.mark.parametrize("code", ["0B35", "0B36"])
def test_realtime_exotic_collection_is_blocked_for_final_holdout(code, race_date):
    policy = classify_jv_odds_evidence(
        code,
        race_date=race_date,
    )
    assert policy.can_be_prebet_quote is False
    assert policy.can_be_strict_ev_input is False
    assert policy.protected_holdout_blocked is True
    assert "must not be read or collected" in policy.reason


def test_unknown_jv_odds_evidence_fails_closed():
    policy = classify_jv_odds_evidence("H6")
    assert policy.evidence_kind == "unknown"
    assert policy.can_be_prebet_quote is False
    assert policy.can_be_strict_ev_input is False
