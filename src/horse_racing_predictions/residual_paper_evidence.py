from __future__ import annotations

from pathlib import Path
import random

from .ledger import Ledger
from .residual_shadow_paper import (
    PAPER_MODEL_VERSION,
    PAPER_POLICY_VERSION,
    summarize_residual_v12_paper,
)


MIN_PROSPECTIVE_EVALUATED_RACES = 500
MIN_SETTLED_PAPER_BETS = 200
MIN_BOOTSTRAP_RACE_CLUSTERS = 20
ROI_BOOTSTRAP_REPLICATES = 5_000
ROI_BOOTSTRAP_SEED = 20260930
ROI_CONFIDENCE_LEVEL = 0.95
RECENT_ROI_WINDOWS = (20, 50, 100)


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        raise ValueError("percentile requires non-empty values")
    if not 0.0 <= quantile <= 1.0:
        raise ValueError("quantile must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(
        ordered[lower] * (1.0 - weight)
        + ordered[upper] * weight
    )


def _race_clustered_roi_bootstrap(ledger: Ledger) -> dict:
    rows = ledger.conn.execute(
        """
        SELECT b.race_id,b.stake_yen,COALESCE(b.payout_yen,0)
        FROM bets b
        JOIN paper_bet_evidence be
          ON be.bet_id=b.id
        JOIN predictions p
          ON p.id=be.prediction_id
        WHERE p.model_version=?
          AND b.stake_yen > 0
          AND b.result IS NOT NULL
        ORDER BY b.id
        """,
        (PAPER_MODEL_VERSION,),
    ).fetchall()

    race_totals: dict[str, list[int]] = {}
    for race_id, stake_yen, payout_yen in rows:
        key = str(race_id)
        values = race_totals.setdefault(key, [0, 0])
        values[0] += int(stake_yen)
        values[1] += int(payout_yen or 0)

    race_clusters = len(race_totals)
    if race_clusters < MIN_BOOTSTRAP_RACE_CLUSTERS:
        return {
            "status": "insufficient_race_clusters",
            "race_clusters": race_clusters,
            "minimum_race_clusters": MIN_BOOTSTRAP_RACE_CLUSTERS,
            "replicates": ROI_BOOTSTRAP_REPLICATES,
            "seed": ROI_BOOTSTRAP_SEED,
            "confidence_level": ROI_CONFIDENCE_LEVEL,
            "roi_ci_lower": None,
            "roi_ci_upper": None,
            "positive_roi_fraction": None,
        }

    clusters = list(race_totals.values())
    count = len(clusters)
    rng = random.Random(ROI_BOOTSTRAP_SEED)
    bootstrap_roi: list[float] = []
    for _ in range(ROI_BOOTSTRAP_REPLICATES):
        total_stake = 0
        total_payout = 0
        for _ in range(count):
            stake_yen, payout_yen = clusters[rng.randrange(count)]
            total_stake += stake_yen
            total_payout += payout_yen
        if total_stake <= 0:
            continue
        bootstrap_roi.append(
            total_payout / total_stake - 1.0
        )

    if not bootstrap_roi:
        return {
            "status": "unavailable",
            "race_clusters": race_clusters,
            "minimum_race_clusters": MIN_BOOTSTRAP_RACE_CLUSTERS,
            "replicates": ROI_BOOTSTRAP_REPLICATES,
            "seed": ROI_BOOTSTRAP_SEED,
            "confidence_level": ROI_CONFIDENCE_LEVEL,
            "roi_ci_lower": None,
            "roi_ci_upper": None,
            "positive_roi_fraction": None,
        }

    alpha = (1.0 - ROI_CONFIDENCE_LEVEL) / 2.0
    lower = _percentile(bootstrap_roi, alpha)
    upper = _percentile(bootstrap_roi, 1.0 - alpha)
    positive_fraction = (
        sum(value > 0.0 for value in bootstrap_roi)
        / len(bootstrap_roi)
    )
    return {
        "status": "available",
        "race_clusters": race_clusters,
        "minimum_race_clusters": MIN_BOOTSTRAP_RACE_CLUSTERS,
        "replicates": len(bootstrap_roi),
        "seed": ROI_BOOTSTRAP_SEED,
        "confidence_level": ROI_CONFIDENCE_LEVEL,
        "roi_ci_lower": float(lower),
        "roi_ci_upper": float(upper),
        "positive_roi_fraction": float(positive_fraction),
    }



def _settled_risk_diagnostics(ledger: Ledger) -> dict:
    rows = ledger.conn.execute(
        """
        SELECT
            b.id,
            b.stake_yen,
            COALESCE(b.payout_yen,0),
            b.result,
            b.decimal_odds
        FROM bets b
        JOIN paper_bet_evidence be
          ON be.bet_id=b.id
        JOIN predictions p
          ON p.id=be.prediction_id
        WHERE p.model_version=?
          AND b.stake_yen > 0
          AND b.result IS NOT NULL
        ORDER BY b.id
        """,
        (PAPER_MODEL_VERSION,),
    ).fetchall()

    settled_count = len(rows)
    if settled_count == 0:
        return {
            "settled_hit_rate": None,
            "average_settled_odds": None,
            "longest_losing_streak": 0,
            "current_losing_streak": 0,
            "recent_roi_windows": [
                {
                    "window_bets": window,
                    "sample_bets": 0,
                    "roi": None,
                }
                for window in RECENT_ROI_WINDOWS
            ],
        }

    wins = 0
    longest_losing_streak = 0
    current_losing_streak = 0
    decimal_odds: list[float] = []

    for _, _, _, result, odds in rows:
        if str(result).upper() == "WIN":
            wins += 1
            current_losing_streak = 0
        else:
            current_losing_streak += 1
            longest_losing_streak = max(
                longest_losing_streak,
                current_losing_streak,
            )
        if odds is not None:
            decimal_odds.append(float(odds))

    recent_roi_windows: list[dict] = []
    for window in RECENT_ROI_WINDOWS:
        sample = rows[-window:]
        stake_yen = sum(int(row[1]) for row in sample)
        payout_yen = sum(int(row[2] or 0) for row in sample)
        recent_roi_windows.append({
            "window_bets": int(window),
            "sample_bets": int(len(sample)),
            "roi": (
                float(payout_yen / stake_yen - 1.0)
                if stake_yen > 0
                else None
            ),
        })

    return {
        "settled_hit_rate": float(wins / settled_count),
        "average_settled_odds": (
            float(sum(decimal_odds) / len(decimal_odds))
            if decimal_odds
            else None
        ),
        "longest_losing_streak": int(longest_losing_streak),
        "current_losing_streak": int(current_losing_streak),
        "recent_roi_windows": recent_roi_windows,
    }

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
        bootstrap = _race_clustered_roi_bootstrap(ledger)
        risk = _settled_risk_diagnostics(ledger)
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
    roi_ci_lower = bootstrap["roi_ci_lower"]
    statistical_positive_roi_evidence = bool(
        sufficient_evidence
        and roi_ci_lower is not None
        and float(roi_ci_lower) > 0.0
    )

    if not sufficient_evidence:
        status = "insufficient_evidence"
    elif statistical_positive_roi_evidence:
        status = "review_ready_statistically_positive_roi"
    elif observed_positive_roi:
        status = "review_ready_positive_observed_roi_inconclusive"
    else:
        status = "review_ready_non_positive_observed_roi"

    return {
        "status": status,
        "policy_version": PAPER_POLICY_VERSION,
        "model_version": PAPER_MODEL_VERSION,
        "thresholds_frozen_before_outcome_review": True,
        "statistical_method_frozen_before_outcome_review": True,
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
        "statistical_positive_roi_evidence": (
            statistical_positive_roi_evidence
        ),
        "roi_bootstrap_status": bootstrap["status"],
        "roi_bootstrap_race_clusters": bootstrap["race_clusters"],
        "roi_bootstrap_minimum_race_clusters": (
            bootstrap["minimum_race_clusters"]
        ),
        "roi_bootstrap_replicates": bootstrap["replicates"],
        "roi_bootstrap_seed": bootstrap["seed"],
        "roi_confidence_level": bootstrap["confidence_level"],
        "roi_ci_lower": bootstrap["roi_ci_lower"],
        "roi_ci_upper": bootstrap["roi_ci_upper"],
        "bootstrap_positive_roi_fraction": (
            bootstrap["positive_roi_fraction"]
        ),
        "selected_bets": int(performance["selected_bets"]),
        "unsettled_bets": int(performance["unsettled_bets"]),
        "wins": int(performance["wins"]),
        "losses": int(performance["losses"]),
        "settled_stake_yen": int(performance["settled_stake_yen"]),
        "payout_yen": int(performance["payout_yen"]),
        "profit_yen": int(performance["profit_yen"]),
        "roi": roi,
        "max_drawdown_yen": int(performance["max_drawdown_yen"]),
        "settled_hit_rate": risk["settled_hit_rate"],
        "average_settled_odds": risk["average_settled_odds"],
        "longest_losing_streak": risk["longest_losing_streak"],
        "current_losing_streak": risk["current_losing_streak"],
        "recent_roi_windows": risk["recent_roi_windows"],
        "risk_diagnostics_adaptive": False,
        "live_execution_enabled": False,
        "automatic_live_promotion": False,
    }
