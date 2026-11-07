"""Private, post-result reconciliation of predeclared *hypothetical* NAR tickets.

Produces a no-market-input paper-ticket ledger, not actual purchases,
historical ROI, a legitimate live betting backtest, or positive EV.
The upstream forecast timestamp/model fit assertions are syntactic and
cannot independently prove that a contemporaneous forecast existed.

All in-scope flat races MUST be payout-consistent. A posthoc omission is
never permitted just to produce a more favorable profit figure.
No ZIP, network, filesystem, public logging, or OOS 2023+ access.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .nar_official_exception_audit import (
    NarOfficialExceptionDetail, NarStatusAwareRace,
)
from .nar_official_zip_probe import UnsafeNarSource
from .nar_economic_settlement_adapter import nar_canonical_race_id
from .oddsfree_ev_research import (
    FrozenOddsFreeForecast, select_top3_and_outsider,
)


@dataclass(frozen=True)
class NarHypotheticalTicket:
    race_id: str = field(repr=False)
    horse_number: str = field(repr=False)
    ticket_type: str
    published_after_event_status: str
    treatment: str
    hypothetical_stake_yen: int
    hypothetical_return_yen: int | None
    hypothetical_only: bool = True
    actual_purchase_proven: bool = False
    independent_preoff_issuance_proven: bool = False


@dataclass(frozen=True)
class NarPaperLedgerAudit:
    status: str
    source_races: int
    predeclared_out_of_scope_races: int
    flat_races: int
    reconciled_flat_races: int
    unresolved_flat_races: int
    expected_tickets: int
    settled_hypothetical_tickets: int
    unoffered_hypothetical_tickets: int
    refunded_hypothetical_tickets: int
    ambiguous_hypothetical_tickets: int
    actual_purchases_verified: bool = False
    independent_preoff_forecasts_verified: bool = False
    realized_roi_available: bool = False
    positive_expected_value_demonstrated: bool = False
    authorized_for_betting: bool = False
    source_bytes_exported: bool = False


@dataclass(frozen=True)
class NarPaperTicketLedger:
    audit: NarPaperLedgerAudit
    tickets: tuple[NarHypotheticalTicket, ...] = field(repr=False)


def _verify_status_race(race: NarStatusAwareRace) -> dict[str, str]:
    """Validate *all* published outcomes, including unselected runners."""
    roster = dict(race.status_by_number)
    ranks = dict(race.rank_by_number)
    win = dict(race.win_yen_by_number)
    place = dict(race.place_yen_by_number)
    if (len(race.status_by_number) != len(roster)
            or not 4 <= len(roster) <= 18
            or set(roster) != set(ranks) or set(roster) != set(win)
            or set(roster) != set(place)
            or not 4 <= race.offered_field_size <= 18
            or not 2 <= race.actual_starting_horses <= race.offered_field_size):
        raise UnsafeNarSource("NAR_PAPER_SETTLEMENT_ROSTER_INVALID")
    cutoff = 2 if race.offered_field_size <= 7 else 3
    started = sold = 0
    for n, status in roster.items():
        rank = ranks[n]
        w, p = win[n], place[n]
        if type(n) is not int or not 1 <= n <= 18:
            raise UnsafeNarSource("NAR_PAPER_HORSE_NUMBER_INVALID")
        if status == "FINISHED":
            if (type(rank) is not int or not 1 <= rank <= 18
                    or type(w) is not int or type(p) is not int
                    or (w >= 100) != (rank == 1)
                    or (p >= 100) != (rank <= cutoff)
                    or (rank != 1 and w != 0)
                    or (rank > cutoff and p != 0)):
                raise UnsafeNarSource("NAR_PAPER_FINISH_OR_PAYOUT_INVALID")
            started += 1
            sold += 1
        elif status == "DNF_NO_REFUND":
            if rank is not None or w != 0 or p != 0:
                raise UnsafeNarSource("NAR_PAPER_DNF_SETTLEMENT_INVALID")
            started += 1
            sold += 1
        elif status == "EXCLUDED_REFUND":
            if rank is not None or w != 100 or p != 100:
                raise UnsafeNarSource("NAR_PAPER_REFUND_SETTLEMENT_INVALID")
            sold += 1
        elif status == "SCRATCH_NOT_OFFERED":
            if rank is not None or w is not None or p is not None:
                raise UnsafeNarSource("NAR_PAPER_SCRATCH_SETTLEMENT_INVALID")
        elif status == "DISQUALIFIED_REVIEW":
            if rank is not None or w is not None or p is not None:
                raise UnsafeNarSource("NAR_PAPER_DQ_SETTLEMENT_INVALID")
            started += 1
            sold += 1
        else:
            raise UnsafeNarSource("NAR_PAPER_UNKNOWN_POSTEVENT_STATUS")
    if (sold != race.offered_field_size or
            started != race.actual_starting_horses):
        raise UnsafeNarSource("NAR_PAPER_PARTICIPANT_COUNTS_INVALID")
    return {str(number): status for number, status in roster.items()}


def _ticket(race_id: str, horse: str, kind: str,
            race: NarStatusAwareRace, status: str) -> NarHypotheticalTicket:
    number = int(horse)
    outcome = (
        dict(race.win_yen_by_number)[number]
        if kind == "WIN" else dict(race.place_yen_by_number)[number]
    )
    if status == "SCRATCH_NOT_OFFERED":
        treatment = "NOT_OFFERED_NO_STAKE"
        stake = 0
        amount = None
    elif status == "EXCLUDED_REFUND":
        treatment = "REFUNDED_PAPER_STAKE"
        stake = 100
        amount = 100
    elif status == "DISQUALIFIED_REVIEW":
        treatment = "UNSETTLED_DISQUALIFICATION"
        stake = 100
        amount = None
    else:
        if type(outcome) is not int or outcome < 0:
            raise UnsafeNarSource("NAR_PAPER_SELECTED_PAYOUT_INVALID")
        treatment = "PAID_WINNER" if outcome else "LOST_AFTER_START"
        stake = 100
        amount = outcome
    return NarHypotheticalTicket(
        race_id=race_id, horse_number=horse, ticket_type=kind,
        published_after_event_status=status, treatment=treatment,
        hypothetical_stake_yen=stake, hypothetical_return_yen=amount,
    )


def reconcile_nar_frozen_paper_ticket_options(
    forecasts: list[FrozenOddsFreeForecast] | tuple[FrozenOddsFreeForecast, ...],
    outcomes: NarOfficialExceptionDetail,
) -> NarPaperTicketLedger:
    """Check two frozen paper picks per race without asserting purchases.

    Strictly train-period only, no protected 2023+ OOS access. Syntactic
    preoff timestamp checks do not establish externally recorded issuance.
    Any unresolved in-scope race blocks the ENTIRE economic ledger.
    """
    if (not isinstance(outcomes, NarOfficialExceptionDetail)
            or outcomes.audit.training_authorized
            or outcomes.audit.economic_roi_authorized
            or outcomes.audit.positive_ev_demonstrated
            or outcomes.audit.source_bytes_exported
            or outcomes.audit.unresolved_flat_races != 0
            or not outcomes.audit.complete_flat_outcome_interpretation
            or not outcomes.validated_races
            or outcomes.audit.status_validated_flat_races
               != len(outcomes.validated_races)
            or outcomes.audit.status_validated_flat_races
               != outcomes.audit.in_scope_flat_races):
        raise UnsafeNarSource("NAR_PAPER_UNRESOLVED_RACE_OR_RIGHTS_HOLD")
    if (not isinstance(forecasts, (list, tuple))
            or len(forecasts) != len(outcomes.validated_races)
            or not 1 <= len(forecasts) <= 20000):
        raise UnsafeNarSource("NAR_PAPER_FULL_FROZEN_RACE_COVERAGE_REQUIRED")
    mapped: dict[str, NarStatusAwareRace] = {}
    statuses: dict[str, dict[str, str]] = {}
    for race in outcomes.validated_races:
        rid = nar_canonical_race_id(race.race_key)
        if rid in mapped or int(race.race_key[1][:4]) not in range(2017, 2023):
            raise UnsafeNarSource("NAR_PAPER_TRAIN_ONLY_NON_DUPLICATE_RACE_REQUIRED")
        mapped[rid] = race
        statuses[rid] = _verify_status_race(race)
    chosen = {}
    for forecast in forecasts:
        if not isinstance(forecast, FrozenOddsFreeForecast):
            raise UnsafeNarSource("NAR_PAPER_FROZEN_FORECAST_REQUIRED")
        if (forecast.race_id in chosen
                or forecast.race_id not in mapped):
            raise UnsafeNarSource("NAR_PAPER_DUPLICATE_OR_MISSING_FORECAST")
        pick = select_top3_and_outsider(forecast)
        rid = forecast.race_id
        if (set(forecast.winner_scores) != set(statuses[rid])
                or set(forecast.outsider_scores) != set(statuses[rid])
                or forecast.race_day.replace("-", "") != mapped[rid].race_key[1]):
            raise UnsafeNarSource("NAR_PAPER_UNVERIFIED_PREOFF_ROSTER_OR_DATE")
        chosen[rid] = pick
    if set(mapped) != set(chosen):
        raise UnsafeNarSource("NAR_PAPER_SELECTIVE_RACE_OMISSION")

    items = []
    for rid in sorted(mapped):
        race = mapped[rid]
        pick = chosen[rid]
        for kind, horse in (("WIN", pick.top3[0]), ("PLACE", pick.outsider)):
            items.append(_ticket(
                rid, horse, kind, race, statuses[rid][horse],
            ))
    return NarPaperTicketLedger(
        audit=NarPaperLedgerAudit(
            status="NAR_COUNTERFACTUAL_PAPER_TICKETS_NO_PURCHASE_PROOF",
            source_races=outcomes.audit.source_races,
            predeclared_out_of_scope_races=outcomes.audit.predeclared_banei_races,
            flat_races=outcomes.audit.in_scope_flat_races,
            reconciled_flat_races=len(mapped), unresolved_flat_races=0,
            expected_tickets=len(items),
            settled_hypothetical_tickets=sum(
                x.treatment in {"PAID_WINNER", "LOST_AFTER_START"}
                for x in items
            ),
            unoffered_hypothetical_tickets=sum(
                x.treatment == "NOT_OFFERED_NO_STAKE" for x in items
            ),
            refunded_hypothetical_tickets=sum(
                x.treatment == "REFUNDED_PAPER_STAKE" for x in items
            ),
            ambiguous_hypothetical_tickets=sum(
                x.treatment == "UNSETTLED_DISQUALIFICATION" for x in items
            ),
        ),
        tickets=tuple(items),
    )
