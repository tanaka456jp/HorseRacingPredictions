from __future__ import annotations

from pathlib import Path

from .ledger import Ledger
from .residual_shadow_paper import (
    PAPER_MODEL_VERSION,
    PAPER_POLICY_VERSION,
    summarize_residual_v12_paper,
)


MIN_PROSPECTIVE_EVALUATED_RACES = 500
MIN_SETTLED_PAPER_BETS = 200


def build_residual_v12_paper_evidence_report(
    ledger_path: str | Path,
) -> dict:
    ledger = Ledger(ledger_path)
    try:
        evaluated_races = int(
            ledger.conn.execute(
                """
                SELECT COUNT(DISTINCT p.race_id)
                FROM predictions p
                JOIN paper_prediction_evidence pe
                  ON pe.prediction_id=p.id
                WHERE p.model_version=?
                """,
                (PAPER_MODEL_VERSION,),
            ).fetchone()[0]
        )
        performance = summarize_residual_v12_paper(ledger)
    finally:
        ledger.close()

    settled_bets = int(performance["settled_bets"])
    enough_races = evaluated_races >= MIN_PROSPECTIVE_EVALUATED_RACES
    enough_bets = settled_bets >= MIN_SETTLED_PAPER_BETS
    sufficient_evidence = bool(enough_races and enough_bets)

    roi = performance["roi"]
    observed_positive_roi = bool(
        roi is not None and float(roi) > 0.0
    )

    if not sufficient_evidence:
        status = "insufficient_evidence"
    elif observed_positive_roi:
        status = "review_ready_positive_observed_roi"
    else:
        status = "review_ready_non_positive_observed_roi"

    return {
        "status": status,
        "policy_version": PAPER_POLICY_VERSION,
        "model_version": PAPER_MODEL_VERSION,
        "thresholds_frozen_before_outcome_review": True,
        "minimum_prospective_evaluated_races": (
            MIN_PROSPECTIVE_EVALUATED_RACES
        ),
        "minimum_settled_paper_bets": MIN_SETTLED_PAPER_BETS,
        "prospective_evaluated_races": evaluated_races,
        "settled_paper_bets": settled_bets,
        "evaluated_race_progress": min(
            1.0,
            evaluated_races / MIN_PROSPECTIVE_EVALUATED_RACES,
        ),
        "settled_bet_progress": min(
            1.0,
            settled_bets / MIN_SETTLED_PAPER_BETS,
        ),
        "sufficient_evidence": sufficient_evidence,
        "observed_positive_roi": observed_positive_roi,
        "selected_bets": int(performance["selected_bets"]),
        "unsettled_bets": int(performance["unsettled_bets"]),
        "wins": int(performance["wins"]),
        "losses": int(performance["losses"]),
        "settled_stake_yen": int(performance["settled_stake_yen"]),
        "payout_yen": int(performance["payout_yen"]),
        "profit_yen": int(performance["profit_yen"]),
        "roi": roi,
        "max_drawdown_yen": int(performance["max_drawdown_yen"]),
        "live_execution_enabled": False,
        "automatic_live_promotion": False,
    }
