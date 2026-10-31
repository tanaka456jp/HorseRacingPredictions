"""Fictional-only odds-independent race payoff research verification."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from dataclasses import replace

import pytest

from horse_racing_predictions.oddsfree_ev_research import (
    FinalRaceSettlement,
    FrozenOddsFreeForecast,
    evaluate_frozen_oddsfree_economics,
    select_top3_and_outsider,
)

UTC = timezone.utc


def fixture_race(*, race: int = 1, field: int = 8, outsider_places=False,
                 event_day="2024-10-27", model_ref="mock-v1"):
    horses = tuple(f"MOCK_HORSE_{i}" for i in range(1, field + 1))
    winner_scores = {h: float(20 - i) for i, h in enumerate(horses, 1)}
    outsider_scores = {
        h: (100.0 if i == 4 else 1.0)
        for i, h in enumerate(horses, 1)
    }
    when = datetime.fromisoformat(f"{event_day}T05:00:00+00:00")
    forecast = FrozenOddsFreeForecast(
        race_id=f"MOCK_{race}", race_day=event_day,
        predicted_at_utc=when - timedelta(hours=2),
        post_time_utc=when, model_ref=model_ref,
        model_fit_through_day="2024-08-31",
        winner_scores=winner_scores, outsider_scores=outsider_scores,
    )
    positions = {h: i for i, h in enumerate(horses, 1)}
    if outsider_places:
        positions[horses[3]] = 2
        positions[horses[1]] = 4
    threshold = 2 if field <= 7 else 3
    final = FinalRaceSettlement(
        race_id=f"MOCK_{race}",
        finishing_positions=positions,
        win_return_per_100_yen={
            h: (350 if pos == 1 else 0) for h, pos in positions.items()
        },
        place_return_per_100_yen={
            h: (120 + 10 * pos if pos <= threshold else 0)
            for h, pos in positions.items()
        },
    )
    return forecast, final


def test_frozen_three_plus_outsider_stable_under_outcome_payout_changes():
    forecast, settled = fixture_race(outsider_places=True)
    chosen = select_top3_and_outsider(forecast)
    assert chosen.top3 == ("MOCK_HORSE_1", "MOCK_HORSE_2", "MOCK_HORSE_3")
    assert chosen.outsider == "MOCK_HORSE_4"
    modified = replace(
        settled,
        win_return_per_100_yen={
            h: (2000 if pos == 1 else 0)
            for h, pos in settled.finishing_positions.items()
        },
    )
    assert select_top3_and_outsider(forecast) == chosen
    a = evaluate_frozen_oddsfree_economics([forecast], [settled],
                                           bootstrap_samples=200)
    b = evaluate_frozen_oddsfree_economics([forecast], [modified],
                                           bootstrap_samples=200)
    assert a.combined_realized_roi != b.combined_realized_roi
    assert a.positive_expected_value_demonstrated is False
    assert b.positive_expected_value_demonstrated is False
    assert a.publication_authorized is False


def test_realized_yen_roi_and_independent_outsider_market_result():
    prediction, outcome = fixture_race(outsider_places=True)
    report = evaluate_frozen_oddsfree_economics(
        [prediction], [outcome], bootstrap_samples=200,
    )
    assert report.races == 1
    assert report.wagers_per_race == 2
    assert report.top1_win_stake_yen == 100
    assert report.top1_win_return_yen == 350
    assert report.outsider_place_stake_yen == 100
    assert report.outsider_place_return_yen == 140
    assert report.combined_stake_yen == 200
    assert report.combined_return_yen == 490
    assert report.combined_realized_roi == pytest.approx(1.45)
    assert report.podium_overlap_rate == pytest.approx(2 / 3)
    assert report.outsider_podium_hit_rate == 1.0
    assert report.status == "RESEARCH_ONLY_REALIZED_RETURNS_NOT_EXPECTED_VALUE"
    assert report.positive_expected_value_demonstrated is False
    assert report.independent_race_days == 1
    assert report.bootstrap_interval_available is False
    assert report.combined_bootstrap_95_lower_roi is None
    assert report.combined_bootstrap_95_upper_roi is None
    assert report.real_source_rights_verified is False


def test_bootstrap_deterministic_and_stays_research_only():
    data = [
        fixture_race(
            race=i, outsider_places=i % 2 == 0,
            event_day=(date(2024, 10, 1) + timedelta(days=i - 1)).isoformat(),
        )
        for i in range(1, 31)
    ]
    preds, outcomes = zip(*data)
    first = evaluate_frozen_oddsfree_economics(list(preds), list(outcomes),
                                               bootstrap_samples=300)
    second = evaluate_frozen_oddsfree_economics(list(preds), list(outcomes),
                                                bootstrap_samples=300)
    assert first == second
    assert first.independent_race_days == 30
    assert first.bootstrap_interval_available is True
    assert first.bootstrap_unit == "race_day"
    assert (first.combined_bootstrap_95_lower_roi
            <= first.combined_realized_roi
            <= first.combined_bootstrap_95_upper_roi)
    assert first.positive_expected_value_demonstrated is False


def test_official_jra_place_rule_five_to_seven_pay_only_top_two():
    f, outcome = fixture_race(field=7)
    result = evaluate_frozen_oddsfree_economics(
        [f], [outcome], bootstrap_samples=200,
    )
    assert result.races == 1
    assert outcome.place_return_per_100_yen["MOCK_HORSE_3"] == 0

    broken = replace(
        outcome,
        place_return_per_100_yen={
            **outcome.place_return_per_100_yen,
            "MOCK_HORSE_3": 140,
        },
    )
    with pytest.raises(ValueError, match="PAYOUT_CONTRADICTS_FINAL_FINISH"):
        evaluate_frozen_oddsfree_economics([f], [broken],
                                            bootstrap_samples=200)


def test_jra_four_runner_race_has_no_place_ticket():
    f, outcome = fixture_race(field=4)
    with pytest.raises(ValueError, match="FINAL_RESULTS_INCOMPLETE"):
        evaluate_frozen_oddsfree_economics([f], [outcome],
                                            bootstrap_samples=200)


def test_early_jst_race_with_previous_utc_day_still_valid():
    f, _ = fixture_race()
    f = replace(
        f,
        post_time_utc=datetime(2024, 10, 26, 23, 30, tzinfo=UTC),
        predicted_at_utc=datetime(2024, 10, 26, 21, tzinfo=UTC),
    )
    assert select_top3_and_outsider(f).outsider == "MOCK_HORSE_4"


def test_post_time_and_price_feature_leakage_refused():
    f, _ = fixture_race()
    with pytest.raises(ValueError, match="UNFROZEN_OR_MARKET_DEPENDENT"):
        select_top3_and_outsider(replace(f, odds_used_in_selection=True))
    with pytest.raises(ValueError, match="FORECAST_MUST_PRECEDE"):
        select_top3_and_outsider(replace(
            f, predicted_at_utc=f.post_time_utc,
        ))
    with pytest.raises(ValueError, match="PROTECTED_FINAL_HOLDOUT"):
        select_top3_and_outsider(replace(f, race_day="2025-01-01"))


def test_mixed_roster_duplicate_settlements_and_model_fails_closed():
    a, outcome_a = fixture_race(race=1)
    b, outcome_b = fixture_race(race=2)
    wrong = replace(outcome_a, finishing_positions={
        **outcome_a.finishing_positions, "EXTRA_HORSE": 9,
    })
    with pytest.raises(ValueError, match="FROZEN_FORECAST_VS_FINAL_FIELD_MISMATCH"):
        evaluate_frozen_oddsfree_economics([a], [wrong],
                                            bootstrap_samples=200)
    with pytest.raises(ValueError, match="DUPLICATE_OR_MISSING_SETTLEMENT"):
        evaluate_frozen_oddsfree_economics([a, b], [outcome_a, outcome_a],
                                            bootstrap_samples=200)
    with pytest.raises(ValueError, match="FROZEN_SINGLE_MODEL_VERSION"):
        evaluate_frozen_oddsfree_economics(
            [a, replace(b, model_ref="new-model")],
            [outcome_a, outcome_b], bootstrap_samples=200,
        )


def test_bet_selection_is_independent_of_horse_finish_rank():
    f, outcome = fixture_race()
    changed = replace(outcome, finishing_positions={
        **outcome.finishing_positions,
        "MOCK_HORSE_1": 2,
        "MOCK_HORSE_2": 1,
    })
    assert select_top3_and_outsider(f) == select_top3_and_outsider(f)
    with pytest.raises(ValueError, match="PAYOUT_CONTRADICTS_FINAL_FINISH"):
        evaluate_frozen_oddsfree_economics([f], [changed],
                                            bootstrap_samples=200)


def test_model_fit_cutoff_must_precede_prediction_event_day():
    f, _ = fixture_race()
    with pytest.raises(ValueError, match="MODEL_MUST_BE_FROZEN_BEFORE_TARGET_RACE"):
        select_top3_and_outsider(
            replace(f, model_fit_through_day=f.race_day)
        )
    with pytest.raises(ValueError, match="MODEL_MUST_BE_FROZEN_BEFORE_TARGET_RACE"):
        select_top3_and_outsider(
            replace(f, model_fit_through_day="2024-12-31")
        )


def test_same_day_many_races_do_not_masquerade_as_many_independent_days():
    data = [fixture_race(race=i, outsider_places=i % 2 == 0)
            for i in range(1, 31)]
    forecasts, final = zip(*data)
    report = evaluate_frozen_oddsfree_economics(
        list(forecasts), list(final), bootstrap_samples=200,
    )
    assert report.races == 30
    assert report.independent_race_days == 1
    assert report.bootstrap_interval_available is False
    assert report.combined_bootstrap_95_lower_roi is None


def test_score_and_settlement_maps_cannot_change_after_freeze():
    f, settlement = fixture_race()
    from_first = dict(f.winner_scores)
    with pytest.raises(TypeError):
        f.winner_scores["MOCK_HORSE_1"] = -1
    with pytest.raises(TypeError):
        settlement.finishing_positions["MOCK_HORSE_1"] = 8
    with pytest.raises(TypeError):
        settlement.place_return_per_100_yen["MOCK_HORSE_2"] = 10000
    assert dict(f.winner_scores) == from_first
    # External caller's own mutable dict is independently copied.
    mutable_scores = dict(from_first)
    mutated = replace(f, winner_scores=mutable_scores)
    mutable_scores["MOCK_HORSE_1"] = -500
    assert mutated.winner_scores["MOCK_HORSE_1"] > 0
    assert select_top3_and_outsider(mutated).top3[0] == "MOCK_HORSE_1"
