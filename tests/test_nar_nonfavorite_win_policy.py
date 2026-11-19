"""No-network fictional tests for preregistered first-favorite exclusion."""
from datetime import datetime, timedelta, timezone

import pytest
from horse_racing_predictions.nar_nonfavorite_win_policy import (
    NonfavoriteEvidenceHold, NonfavoriteWinRace,
    compare_nonfavorite_win_policies,
)

JST = timezone(timedelta(hours=9))


def fixture(day=19):
    off = datetime(2026, 11, day, 15, tzinfo=JST)
    return off


def race(i, rank, *, day=19, payout=0, status="FINISHED",
         source_delay=30, odds=3.0):
    off = fixture(day)
    return NonfavoriteWinRace(
        race_id=f"TEST:{day}:{i:02d}",
        race_day_jst=f"2026-11-{day:02d}",
        top_win_horse="7",
        entrants=10,
        forecast_frozen_utc=off - timedelta(hours=3),
        hosted_forecast_receipt_utc=off - timedelta(hours=2),
        scheduled_off_utc=off,
        selected_preoff_popularity=rank,
        selected_preoff_win_odds=odds,
        official_market_source_utc=off - timedelta(minutes=source_delay + 1),
        locally_received_market_utc=off - timedelta(minutes=source_delay),
        settlement_status=status,
        official_win_return_per_100_yen=payout,
    )


def evaluate(*entries):
    return compare_nonfavorite_win_policies(
        {x.race_id: x.race_day_jst for x in entries}, list(entries)
    )


def test_nonfavorite_policy_can_improve_despite_lower_staking():
    a=evaluate(race(1,1,payout=200),race(2,3,payout=600),
               race(3,1,payout=0))
    assert a.status.startswith("COMPLETE_RETROSPECTIVE")
    assert a.frozen_races==3
    assert a.first_favorite_predictions==2
    assert a.nonfavorite_predictions==1
    assert a.full_policy_hypothetical_stake_yen==300
    assert a.full_policy_official_return_yen==800
    assert a.nonfavorite_policy_hypothetical_stake_yen==100
    assert a.nonfavorite_policy_official_return_yen==600
    assert round(a.full_policy_paper_roi,5)==round(5/3,5)
    assert a.nonfavorite_policy_paper_roi==5.0
    assert a.roi_change_percentage_points>0
    assert a.after_cost_positive_expected_value_proven is False
    assert a.market_execution_verified is False


def test_excluding_favorite_can_also_make_outcome_worse():
    a=evaluate(race(1,1,payout=900),race(2,4,payout=0))
    assert a.full_policy_paper_roi==3.5
    assert a.nonfavorite_policy_paper_roi==-1
    assert a.roi_change_percentage_points<0


def test_only_favorites_mean_zero_eligible_filtered_stake_and_hold():
    a=evaluate(race(1,1,payout=230),race(2,1,payout=0))
    assert a.status.startswith("HOLD")
    assert a.nonfavorite_policy_paper_roi is None
    assert a.full_policy_paper_roi is None


@pytest.mark.parametrize("missing",[
    {"selected_preoff_popularity":None},
    {"selected_preoff_win_odds":None},
    {"selected_preoff_popularity":0},
    {"selected_preoff_popularity":True},
    {"selected_preoff_popularity":11},
    {"selected_preoff_win_odds":float("nan")},
    {"selected_preoff_win_odds":float("inf")},
    {"selected_preoff_win_odds":0.8},
    {"hosted_forecast_receipt_utc":None},
    {"official_market_source_utc":None},
])
def test_unverified_popularity_does_not_generate_cherrypicked_roi(missing):
    from dataclasses import replace
    valid=race(1,2,payout=600)
    corrupt=replace(race(2,1,payout=200),**missing)
    a=evaluate(valid,corrupt)
    assert a.frozen_races==2
    assert a.missing_or_unverifiable_preoff_prices==1
    assert a.full_policy_paper_roi is None
    assert a.nonfavorite_policy_paper_roi is None


def test_postoff_popularity_never_passes_even_if_final_payout_known():
    from dataclasses import replace
    original=race(1,2,payout=600)
    final=replace(original,
        locally_received_market_utc=original.scheduled_off_utc+timedelta(minutes=1),
        official_market_source_utc=original.scheduled_off_utc)
    a=evaluate(final)
    assert a.missing_or_unverifiable_preoff_prices==1
    assert a.status.startswith("HOLD")


def test_late_quote_and_stale_market_source_rejected():
    a=evaluate(race(1,3,source_delay=10,payout=500))
    assert a.status.startswith("HOLD")
    from dataclasses import replace
    src=race(1,3,payout=500)
    stale=replace(src,official_market_source_utc=src.scheduled_off_utc-timedelta(hours=1))
    assert evaluate(stale).status.startswith("HOLD")


def test_unregistered_duplicate_and_missing_race_never_change_frozen_denominator():
    observations=[race(1,2,payout=500)]
    d={x.race_id:x.race_day_jst for x in observations}
    d["TEST:19:02"]="2026-11-19"
    result=compare_nonfavorite_win_policies(d,observations)
    assert result.frozen_races==2
    assert result.missing_or_unverifiable_preoff_prices==1
    assert result.unresolved_settlements==1
    assert result.full_policy_paper_roi is None
    with pytest.raises(NonfavoriteEvidenceHold,match="DUPLICATE"):
        compare_nonfavorite_win_policies(d,observations*2)
    with pytest.raises(NonfavoriteEvidenceHold,match="UNREGISTERED"):
        compare_nonfavorite_win_policies(d,observations+[race(7,2,payout=0)])


def test_refunds_scratches_and_unknown_settlements_are_not_wins():
    a=evaluate(
        race(1,1,payout=100,status="EXCLUDED_REFUND"),
        race(2,3,payout=None,status="SCRATCH_NOT_OFFERED"),
        race(3,2,payout=0,status="DNF_NO_REFUND"),
    )
    assert a.full_policy_hypothetical_stake_yen==200
    assert a.nonfavorite_policy_hypothetical_stake_yen==100
    assert a.nonfavorite_policy_paper_roi==-1
    assert a.selected_nonfavorite_bets==1
    assert a.actual_tickets_purchased is False
    from dataclasses import replace
    unknown=replace(race(1,3,payout=200),settlement_status="UNKNOWN")
    assert evaluate(unknown).status.startswith("HOLD")


def test_bootstrap_is_day_clustered_and_descriptive_only():
    entries=[race(i,1 if i%2 else 3,day=day,
                  payout=220 if i%2 else 0)
             for day in range(1,22) for i in range(1,3)]
    a=evaluate(*entries)
    assert a.evaluated_race_days==21
    assert a.day_clustered_descriptive_roi_difference_ci95 is not None
    assert a.day_clustered_descriptive_roi_difference_ci95[0] < 0
    assert a.after_cost_positive_expected_value_proven is False


def test_model_top_pick_must_be_frozen_before_market_and_off():
    from dataclasses import replace
    before=race(1,2,payout=0)
    after=replace(before,forecast_frozen_utc=before.scheduled_off_utc)
    with pytest.raises(NonfavoriteEvidenceHold,match="INVALID_FROZEN"):
        evaluate(after)
