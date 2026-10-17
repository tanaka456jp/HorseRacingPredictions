from __future__ import annotations

from copy import deepcopy

from horse_racing_predictions.exotic_prebet_execution_triage import (
    triage_exotic_prebet_execution,
)


def _source() -> dict:
    return {
        "provider_name": "Synthetic Free Source",
        "terms_reference": "https://example.invalid/terms",
        "source_reference": "https://example.invalid/odds",
        "race_id_mapping": "synthetic stable race key",
        "combination_mapping": "trio sorted; trifecta ordered",
        "capture_clock_evidence": "synthetic UTC source clock",
        "purchase_cutoff_reference": "https://example.invalid/cutoff",
        "retention_policy_reference": "https://example.invalid/retention",
        "free_access_confirmed": True,
        "automated_capture_permitted": True,
        "ml_research_permitted": True,
        "snapshot_retention_permitted": True,
        "pre_decision_quotes_available": True,
        "purchase_availability_verified": True,
        "immutable_capture_supported": True,
        "provider_refresh_seconds": 60,
        "access_cost_yen": 0,
        "rights_reviewed_at": "2026-10-10T00:00:00+00:00",
        "source_kind": "official_public",
    }


def _quote() -> dict:
    return {
        "race_id": "2024-12-31:R11",
        "bet_type": "trio",
        "horse_numbers": [7, 2, 11],
        "decimal_odds": "42.5",
        "source_name": "Synthetic Free Source",
        "source_reference": "https://example.invalid/odds",
        "quote_stage": "pre_race",
        "odds_kind": "decimal_quote",
        "observed_at": "2024-12-31T05:28:30+00:00",
        "captured_at": "2024-12-31T05:28:40+00:00",
        "scheduled_post_time": "2024-12-31T05:30:00+00:00",
    }


def test_execution_triage_never_auto_approves_even_structurally_valid_evidence():
    result = triage_exotic_prebet_execution(
        _quote(),
        _source(),
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )

    assert result["status"] == "human_review_required"
    assert result["blockers"] == []
    assert result["canonical_combination_key"] == (
        "2024-12-31:R11:trio:2-7-11"
    )
    assert result["approved_for_acquisition"] is False
    assert result["approved_for_ev"] is False
    assert result["approved_for_paper_staking"] is False


def test_execution_triage_blocks_stale_quote_against_documented_refresh_cadence():
    quote = _quote()
    quote["observed_at"] = "2024-12-31T05:27:30+00:00"

    result = triage_exotic_prebet_execution(
        quote,
        _source(),
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )

    assert result["status"] == "blocked"
    assert "quote exceeds documented refresh cadence" in result["blockers"]
    assert result["canonical_combination_key"] is None


def test_execution_triage_blocks_cutoff_not_between_decision_and_post():
    result = triage_exotic_prebet_execution(
        _quote(),
        _source(),
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:28:59+00:00",
    )

    assert result["status"] == "blocked"
    assert (
        "purchase cutoff must fall between decision and scheduled post"
        in result["blockers"]
    )


def test_execution_triage_blocks_cutoff_at_or_after_scheduled_post():
    for cutoff in (
        "2024-12-31T05:30:00+00:00",
        "2024-12-31T05:30:01+00:00",
    ):
        result = triage_exotic_prebet_execution(
            _quote(),
            _source(),
            decision_at="2024-12-31T05:29:00+00:00",
            purchase_cutoff_at=cutoff,
        )
        assert result["status"] == "blocked"
        assert (
            "purchase cutoff must fall between decision and scheduled post"
            in result["blockers"]
        )


def test_execution_triage_blocks_source_name_or_reference_mismatch():
    quote = _quote()
    source = _source()
    quote["source_name"] = "Different Provider"
    quote["source_reference"] = "https://example.invalid/different"

    result = triage_exotic_prebet_execution(
        quote,
        source,
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )

    assert result["status"] == "blocked"
    assert "source name mismatch" in result["blockers"]
    assert "source reference mismatch" in result["blockers"]


def test_execution_triage_blocks_invalid_or_unknown_refresh_cadence():
    for cadence in (None, 0, -1, 86401, 30.0):
        source = _source()
        source["provider_refresh_seconds"] = cadence

        result = triage_exotic_prebet_execution(
            _quote(),
            source,
            decision_at="2024-12-31T05:29:00+00:00",
            purchase_cutoff_at="2024-12-31T05:29:30+00:00",
        )

        assert result["status"] == "blocked"
        assert any(
            "refresh cadence" in blocker
            for blocker in result["blockers"]
        )


def test_execution_triage_blocks_result_or_final_payout_fields():
    for prohibited in (
        "payout",
        "final_payout",
        "settlement",
        "result",
        "finish_position",
        "final_odds",
    ):
        quote = _quote()
        quote[prohibited] = "forbidden"

        result = triage_exotic_prebet_execution(
            quote,
            _source(),
            decision_at="2024-12-31T05:29:00+00:00",
            purchase_cutoff_at="2024-12-31T05:29:30+00:00",
        )

        assert result["status"] == "blocked"
        assert any(
            "result/final-payout fields are forbidden" in blocker
            for blocker in result["blockers"]
        )


def test_execution_triage_blocks_unverified_source_rights():
    source = _source()
    source["automated_capture_permitted"] = False
    source["ml_research_permitted"] = False
    source["snapshot_retention_permitted"] = False

    result = triage_exotic_prebet_execution(
        _quote(),
        source,
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )

    assert result["status"] == "blocked"
    assert any(
        "automated_capture_permitted" in blocker
        for blocker in result["blockers"]
    )
    assert any(
        "ml_research_permitted" in blocker
        for blocker in result["blockers"]
    )
    assert any(
        "snapshot_retention_permitted" in blocker
        for blocker in result["blockers"]
    )
    assert result["approved_for_ev"] is False


def test_execution_triage_does_not_mutate_inputs():
    source = _source()
    quote = _quote()
    source_before = deepcopy(source)
    quote_before = deepcopy(quote)

    triage_exotic_prebet_execution(
        quote,
        source,
        decision_at="2024-12-31T05:29:00+00:00",
        purchase_cutoff_at="2024-12-31T05:29:30+00:00",
    )

    assert source == source_before
    assert quote == quote_before
