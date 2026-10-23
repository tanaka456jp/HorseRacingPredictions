from __future__ import annotations

from pathlib import Path
from datetime import datetime
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


def _audit_settlement_evidence(ledger: Ledger) -> dict:
    """Audit structural consistency; this is NOT an economic EV gate."""
    rows = ledger.conn.execute(
        """
        SELECT
            b.race_id,b.horse_id,b.result,b.payout_yen,
            b.model_version,p.model_version,
            se.bet_id,se.race_id,se.horse_id,se.result,
            se.payout_yen,se.source,be.bet_id,
            pe.prediction_id,s.id,p.predicted_at,s.observed_at,
            s.scheduled_post_time,s.race_id,s.horse_id,
            p.decimal_odds,s.decimal_odds,s.source,
            b.placed_at,be.recorded_at
        FROM bets b
        LEFT JOIN paper_bet_evidence be ON be.bet_id=b.id
        LEFT JOIN predictions p ON p.id=be.prediction_id
        LEFT JOIN paper_prediction_evidence pe ON pe.prediction_id=p.id
        LEFT JOIN pre_race_odds_snapshots s ON s.id=pe.odds_snapshot_id
        LEFT JOIN paper_settlement_evidence se ON se.bet_id=b.id
        WHERE b.model_version=?
          AND b.stake_yen > 0
          AND b.result IS NOT NULL
        ORDER BY b.id
        """,
        (PAPER_MODEL_VERSION,),
    ).fetchall()
    missing = 0
    missing_bet_evidence = 0
    missing_snapshot_evidence = 0
    invalid_pre_race_evidence = 0
    invalid_paper_record_timing = 0
    inconsistent = 0
    model_mismatch = 0
    for row in rows:
        if row[12] is None:
            missing_bet_evidence += 1
        if row[4] != row[5]:
            model_mismatch += 1
        if row[13] is None or row[14] is None:
            missing_snapshot_evidence += 1
        else:
            try:
                predicted = datetime.fromisoformat(row[15])
                observed = datetime.fromisoformat(row[16])
                post = datetime.fromisoformat(row[17])
                valid_timing = bool(
                    predicted.utcoffset() is not None
                    and observed.utcoffset() is not None
                    and post.utcoffset() is not None
                    and observed <= predicted < post
                )
            except (TypeError, ValueError):
                valid_timing = False
            if (
                not valid_timing
                or row[0] != row[18]
                or row[1] != row[19]
                or row[20] is None
                or row[21] is None
                or abs(float(row[20]) - float(row[21])) > 1e-12
                or not str(row[22] or "").strip()
            ):
                invalid_pre_race_evidence += 1
        # Internal record timestamps must also precede the scheduled post.
        # This is a diagnostic, NOT proof of receipt or broker acceptance.
        if row[13] is not None and row[14] is not None:
            try:
                predicted = datetime.fromisoformat(row[15])
                post = datetime.fromisoformat(row[17])
                placed = datetime.fromisoformat(row[23])
                linked = datetime.fromisoformat(row[24])
                valid_record_clock = bool(
                    all(value.utcoffset() is not None for value in
                        (predicted, post, placed, linked))
                    and predicted <= placed <= linked < post
                )
            except (TypeError, ValueError):
                valid_record_clock = False
            if not valid_record_clock:
                invalid_paper_record_timing += 1
        if row[6] is None:
            missing += 1
        elif (
            row[0] != row[7]
            or row[1] != row[8]
            or row[2] != row[9]
            or int(row[3] or 0) != int(row[10] or 0)
            or not str(row[11] or "").strip()
        ):
            inconsistent += 1
    return {
        "settled_bets_checked": len(rows),
        "missing_settlement_evidence": missing,
        "missing_bet_evidence": missing_bet_evidence,
        "missing_snapshot_evidence": missing_snapshot_evidence,
        "invalid_pre_race_evidence": invalid_pre_race_evidence,
        "invalid_paper_record_timing": invalid_paper_record_timing,
        "paper_record_clock_consistent": bool(
            rows and not (
                missing_bet_evidence or missing_snapshot_evidence
                or invalid_pre_race_evidence or invalid_paper_record_timing
            )
        ),
        "inconsistent_settlement_evidence": inconsistent,
        "prediction_model_mismatches": model_mismatch,
        "structurally_consistent": bool(
            rows and not (
                missing or missing_bet_evidence or missing_snapshot_evidence
                or invalid_pre_race_evidence or inconsistent or model_mismatch
            )
        ),
        "official_payout_provenance_verified": False,
        "actual_purchase_acceptance_verified": False,
        "economic_go_assessed": False,
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
        settlement_audit = _audit_settlement_evidence(ledger)
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
    # A positive legacy bootstrap is not review-ready when any settled
    # Paper bet lacks internally consistent settlement evidence.  This
    # structural gate does NOT verify official payout provenance, execution,
    # licensing, market-relative net ROI, or economic GO.
    statistical_positive_roi_evidence = bool(
        sufficient_evidence
        and settlement_audit["structurally_consistent"]
        and roi_ci_lower is not None
        and float(roi_ci_lower) > 0.0
    )

    if not sufficient_evidence:
        status = "insufficient_evidence"
    elif not settlement_audit["structurally_consistent"]:
        # Legacy ROI remains diagnostic, never review-ready without the
        # complete bet-to-prediction and settlement-evidence chain.
        status = "blocked_unverified_settlement_evidence"
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
        "settlement_evidence_audit": settlement_audit,
        "risk_diagnostics_adaptive": False,
        "live_execution_enabled": False,
        "automatic_live_promotion": False,
    }
