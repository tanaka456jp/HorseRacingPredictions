"""Only fabricated races and hypothetical forecasts; never licensed real data."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_official_exception_audit import (
    audit_nar_official_exceptions,
)
from horse_racing_predictions.nar_status_aware_paper_ticket_ledger import (
    reconcile_nar_frozen_paper_ticket_options,
)
from horse_racing_predictions.oddsfree_ev_research import FrozenOddsFreeForecast
from test_nar_published_result_normalizer import _fixture
from test_nar_official_exception_audit import _synthetic_with_status

JST = timezone(timedelta(hours=9))


def _forecast(*, top=1, outsider=4, month="201711", horses_count=8):
    # By construction: the first three top-scored horses cannot include the
    # separately chosen outsider, even if top/outsider numbers vary.
    horses = [str(n) for n in range(1, horses_count + 1)]
    top_rest = [n for n in horses if n not in (str(top), str(outsider))][:2]
    score = {n: 1.0 for n in horses}
    score[str(top)] = 100.0
    score[top_rest[0]] = 80.0
    score[top_rest[1]] = 70.0
    outsider_score = {n: (90.0 if n == str(outsider) else 1.0) for n in horses}
    day = f"{month[:4]}-{month[4:]}-14"
    post = datetime.fromisoformat(day + "T14:00:00+09:00")
    return FrozenOddsFreeForecast(
        race_id=f"NAR:{month}14:架空競馬場:03",
        race_day=day,
        post_time_utc=post,
        predicted_at_utc=post - timedelta(days=1),
        model_ref="FICTIONAL_FROZEN_RESEARCH_ONLY",
        model_fit_through_day=f"{month[:4]}-10-31",
        winner_scores=score,
        outsider_scores=outsider_score,
    )


def _run(sample, *, top=1, outsider=4):
    normalized = audit_nar_official_exceptions(sample, month="201711")
    return reconcile_nar_frozen_paper_ticket_options(
        [_forecast(top=top, outsider=outsider)], normalized,
    )


def test_full_coverage_fictional_paid_and_losing_tickets():
    report = _run(_fixture(month="201711", with_header=True), top=1, outsider=3)
    a = report.audit
    assert a.source_races == a.flat_races == a.reconciled_flat_races == 1
    assert a.unresolved_flat_races == 0
    assert a.expected_tickets == a.settled_hypothetical_tickets == 2
    assert (a.unoffered_hypothetical_tickets, a.refunded_hypothetical_tickets,
            a.ambiguous_hypothetical_tickets) == (0, 0, 0)
    assert {x.ticket_type for x in report.tickets} == {"WIN", "PLACE"}
    assert [(x.treatment, x.hypothetical_stake_yen,
             x.hypothetical_return_yen) for x in report.tickets] == [
        ("PAID_WINNER", 100, 250), ("PAID_WINNER", 100, 130)
    ]
    assert not a.actual_purchases_verified
    assert not a.independent_preoff_forecasts_verified
    assert not a.realized_roi_available
    assert not a.positive_expected_value_demonstrated
    assert not a.authorized_for_betting
    assert "架空" not in repr(report)


@pytest.mark.parametrize(("marker", "expected_treatment", "stake", "cash"), [
    ("取消", "NOT_OFFERED_NO_STAKE", 0, None),
    ("除外", "REFUNDED_PAPER_STAKE", 100, 100),
    ("中止", "LOST_AFTER_START", 100, 0),
    ("失格", "UNSETTLED_DISQUALIFICATION", 100, None),
])
def test_paper_selection_distinguishes_unavailable_refund_loss_and_dq(
    marker, expected_treatment, stake, cash,
):
    case = _synthetic_with_status(
        marker, only_two_placers=(marker == "取消")
    )
    report = _run(case, top=8, outsider=4)
    ticket = next(t for t in report.tickets if t.ticket_type == "WIN")
    assert ticket.treatment == expected_treatment
    assert ticket.hypothetical_stake_yen == stake
    assert ticket.hypothetical_return_yen == cash
    assert not ticket.actual_purchase_proven
    assert not ticket.independent_preoff_issuance_proven
    assert not report.audit.realized_roi_available
    assert not report.audit.positive_expected_value_demonstrated
    assert report.audit.expected_tickets == 2


def test_refund_selected_as_outsider_is_not_bad_place_prediction():
    case = _synthetic_with_status("除外")
    report = _run(case, top=1, outsider=8)
    top, other = report.tickets
    assert top.ticket_type == "WIN"
    assert top.treatment == "PAID_WINNER"
    assert other.ticket_type == "PLACE"
    assert other.treatment == "REFUNDED_PAPER_STAKE"
    assert other.hypothetical_return_yen == 100
    assert report.audit.refunded_hypothetical_tickets == 1
    assert report.audit.settled_hypothetical_tickets == 1


def test_one_unresolved_race_prevents_all_retrospective_paper_profit():
    import csv
    from io import StringIO
    case = _fixture(month="201711", with_header=True)
    rows = list(csv.reader(StringIO(case["payback"])))
    rows[1][4] = "2"
    sink = StringIO(newline="")
    csv.writer(sink).writerows(rows)
    case["payback"] = sink.getvalue()
    result = audit_nar_official_exceptions(case, month="201711")
    assert result.audit.unresolved_flat_races == 1
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_UNRESOLVED_RACE_OR_RIGHTS_HOLD"):
        reconcile_nar_frozen_paper_ticket_options([_forecast()], result)


def test_false_historical_roster_or_forecast_timestamp_blocks_assessment():
    result = audit_nar_official_exceptions(
        _fixture(month="201711", with_header=True), month="201711",
    )
    guess = _forecast()
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_UNVERIFIED_PREOFF_ROSTER_OR_DATE"):
        reconcile_nar_frozen_paper_ticket_options(
            [replace(guess, winner_scores={str(i): 1.0 for i in range(1, 7)},
                     outsider_scores={str(i): 1.0 for i in range(1, 7)})],
            result,
        )
    with pytest.raises(ValueError, match="FORECAST_MUST_PRECEDE_RACE_OFF"):
        reconcile_nar_frozen_paper_ticket_options(
            [replace(guess, predicted_at_utc=guess.post_time_utc)], result,
        )


def test_forged_paid_winner_return_is_rejected_before_paper_ticket_join():
    result = audit_nar_official_exceptions(
        _fixture(month="201711", with_header=True), month="201711",
    )
    race = result.validated_races[0]
    forged = replace(race, win_yen_by_number=tuple(
        (number, 0) if number == 1 else (number, yen)
        for number, yen in race.win_yen_by_number
    ))
    tainted = replace(result, validated_races=(forged,))
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_FINISH_OR_PAYOUT_INVALID"):
        reconcile_nar_frozen_paper_ticket_options([_forecast()], tainted)


def test_protected_oos_source_rejected_even_with_artificial_frozen_preoff():
    sample = _fixture(month="202402", with_header=True)
    result = audit_nar_official_exceptions(sample, month="202402")
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_TRAIN_ONLY_NON_DUPLICATE_RACE_REQUIRED"):
        reconcile_nar_frozen_paper_ticket_options(
            [_forecast()], result,
        )


def test_false_source_approval_cannot_silently_unlock_real_money_roi():
    result = audit_nar_official_exceptions(
        _fixture(month="201711", with_header=True), month="201711",
    )
    forged = replace(result, audit=replace(
        result.audit, economic_roi_authorized=True,
    ))
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_UNRESOLVED_RACE_OR_RIGHTS_HOLD"):
        reconcile_nar_frozen_paper_ticket_options([_forecast()], forged)


def test_four_offered_horses_do_not_acquire_invented_place_payouts():
    import csv
    from io import StringIO
    case = _fixture(starters=5, month="201711", with_header=True)
    horses = list(csv.reader(StringIO(case["horselist"])))
    horses[5][31] = ""
    horses[5][33] = "取消"
    out = StringIO(newline="")
    csv.writer(out).writerows(horses)
    case["horselist"] = out.getvalue()
    pays = list(csv.reader(StringIO(case["payback"])))
    for index in (7, 8, 10, 11, 13, 14):
        pays[1][index] = ""
    out = StringIO(newline="")
    csv.writer(out).writerows(pays)
    case["payback"] = out.getvalue()
    audited = audit_nar_official_exceptions(case, month="201711")
    assert audited.audit.status_validated_flat_races == 1
    race = audited.validated_races[0]
    assert race.offered_field_size == 4
    assert all(amount in (0, None) for _, amount in race.place_yen_by_number)
    ledger = reconcile_nar_frozen_paper_ticket_options(
        [_forecast(top=1, outsider=5, horses_count=5)], audited
    )
    assert ledger.audit.expected_tickets == 2
    assert ledger.tickets[0].treatment == "PAID_WINNER"
    assert ledger.tickets[1].treatment == "NOT_OFFERED_NO_STAKE"
    assert ledger.tickets[1].hypothetical_stake_yen == 0
    assert not ledger.audit.realized_roi_available


def test_official_winner_payout_on_disqualified_runner_blocks_all_paper_tickets():
    # Mirrors only the STRUCTURE of the one private 2017-11 anomaly.
    # No original runner/race names, payout values or identities are used.
    import csv
    from io import StringIO
    case = _synthetic_with_status("失格")
    pay = list(csv.reader(StringIO(case["payback"])))
    pay[1][4] = "8"  # disqualified runner rather than numeric-rank winner
    out = StringIO(newline="")
    csv.writer(out).writerows(pay)
    case["payback"] = out.getvalue()
    audited = audit_nar_official_exceptions(case, month="201711")
    assert audited.audit.unresolved_reason_counts == (
        ("NAR_WIN_PAYOUT_TO_DISQUALIFIED_STATUS", 1),
    )
    with pytest.raises(UnsafeNarSource, match="NAR_PAPER_UNRESOLVED_RACE_OR_RIGHTS_HOLD"):
        reconcile_nar_frozen_paper_ticket_options(
            [_forecast(top=8, outsider=4)], audited,
        )
