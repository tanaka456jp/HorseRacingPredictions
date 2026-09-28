from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import StrategyConfig
from .domain import HorsePrediction
from .ledger import Ledger
from .market_residual_v12_holdout import FIXED_GAMMA
from .paper_session import PaperTradingSession
from .snapshots import PreRaceOddsSnapshot


PAPER_POLICY_VERSION = "residual-v12-paper-v1"
PAPER_MODEL_VERSION = "shadow-market-residual-v12-paper-v1"
PAPER_MIN_EV = 1.15
PAPER_MIN_PROBABILITY = 0.03
PAPER_FRACTIONAL_KELLY = 0.25
PAPER_MAX_RACE_FRACTION = 0.02
PAPER_MAX_DAY_FRACTION = 0.08
PAPER_MAX_BET_YEN = 10_000
PAPER_MIN_BET_YEN = 100
PAPER_BET_UNIT_YEN = 100


def residual_v12_paper_config() -> StrategyConfig:
    """Return the frozen prospective Paper v1 policy.

    This policy is intentionally fixed before future evaluation. It must not
    be tuned from already-observed forward outcomes.
    """
    return StrategyConfig(
        min_ev=PAPER_MIN_EV,
        min_probability=PAPER_MIN_PROBABILITY,
        min_confidence=0.0,
        fractional_kelly=PAPER_FRACTIONAL_KELLY,
        max_race_fraction=PAPER_MAX_RACE_FRACTION,
        max_day_fraction=PAPER_MAX_DAY_FRACTION,
        max_bet_yen=PAPER_MAX_BET_YEN,
        min_bet_yen=PAPER_MIN_BET_YEN,
        bet_unit_yen=PAPER_BET_UNIT_YEN,
        live_execution_enabled=False,
    )


def _aware_datetime(value, name: str) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return stamp.to_pydatetime()


def _existing_prediction_for_snapshot(
    ledger: Ledger,
    *,
    race_id: str,
    horse_id: str,
    observed_at: datetime,
    source: str,
) -> tuple[int, float, float] | None:
    rows = ledger.conn.execute(
        """
        SELECT p.id,p.predicted_win_probability,p.decimal_odds
        FROM predictions p
        JOIN paper_prediction_evidence pe
          ON pe.prediction_id=p.id
        JOIN pre_race_odds_snapshots s
          ON s.id=pe.odds_snapshot_id
        WHERE p.race_id=?
          AND p.horse_id=?
          AND p.model_version=?
          AND s.observed_at=?
          AND s.source=?
        ORDER BY p.id
        """,
        (
            race_id,
            horse_id,
            PAPER_MODEL_VERSION,
            observed_at.isoformat(),
            source,
        ),
    ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise ValueError(
            "duplicate Residual v12 Paper evidence exists for one snapshot"
        )
    row = rows[0]
    return int(row[0]), float(row[1]), float(row[2])


def _existing_exposures(ledger: Ledger) -> list[dict]:
    rows = ledger.conn.execute(
        """
        SELECT s.scheduled_post_time,b.race_id,b.stake_yen
        FROM bets b
        JOIN paper_bet_evidence be
          ON be.bet_id=b.id
        JOIN paper_prediction_evidence pe
          ON pe.prediction_id=be.prediction_id
        JOIN pre_race_odds_snapshots s
          ON s.id=pe.odds_snapshot_id
        WHERE b.model_version=?
          AND b.stake_yen > 0
        ORDER BY b.id
        """,
        (PAPER_MODEL_VERSION,),
    ).fetchall()
    return [
        {
            "scheduled_post_time": _aware_datetime(row[0], "scheduled_post_time"),
            "race_id": str(row[1]),
            "stake_yen": int(row[2]),
        }
        for row in rows
    ]


def summarize_residual_v12_paper(ledger: Ledger) -> dict:
    rows = ledger.conn.execute(
        """
        SELECT b.id,b.stake_yen,b.payout_yen,b.result
        FROM bets b
        JOIN paper_bet_evidence be
          ON be.bet_id=b.id
        WHERE b.model_version=?
          AND b.stake_yen > 0
        ORDER BY b.id
        """,
        (PAPER_MODEL_VERSION,),
    ).fetchall()

    settled = [row for row in rows if row[3] is not None]
    settled_stake = sum(int(row[1]) for row in settled)
    payout = sum(int(row[2] or 0) for row in settled)
    profit = payout - settled_stake

    cumulative_profit = 0
    peak = 0
    max_drawdown = 0
    wins = 0
    for row in settled:
        stake = int(row[1])
        row_payout = int(row[2] or 0)
        cumulative_profit += row_payout - stake
        peak = max(peak, cumulative_profit)
        max_drawdown = max(max_drawdown, peak - cumulative_profit)
        if row[3] == "WIN":
            wins += 1

    return {
        "policy_version": PAPER_POLICY_VERSION,
        "model_version": PAPER_MODEL_VERSION,
        "selected_bets": int(len(rows)),
        "settled_bets": int(len(settled)),
        "unsettled_bets": int(len(rows) - len(settled)),
        "wins": int(wins),
        "losses": int(len(settled) - wins),
        "settled_stake_yen": int(settled_stake),
        "payout_yen": int(payout),
        "profit_yen": int(profit),
        "roi": (
            float(payout / settled_stake - 1.0)
            if settled_stake > 0
            else None
        ),
        "max_drawdown_yen": int(max_drawdown),
    }


def run_residual_v12_forward_paper(
    predictions: pd.DataFrame,
    *,
    ledger_path: str | Path,
    bankroll_yen: int = 100_000,
    decision_time: datetime | None = None,
) -> dict:
    if bankroll_yen <= 0:
        raise ValueError("bankroll_yen must be positive")
    if predictions.empty:
        raise ValueError("Residual v12 Paper predictions are empty")

    fixed_gamma = pd.to_numeric(
        predictions["fixed_gamma"],
        errors="raise",
    )
    if not fixed_gamma.eq(float(FIXED_GAMMA)).all():
        raise ValueError(
            "Residual v12 Paper must use frozen gamma=4.0"
        )

    decision_time = decision_time or datetime.now(timezone.utc)
    if (
        decision_time.tzinfo is None
        or decision_time.utcoffset() is None
    ):
        raise ValueError("decision_time must be timezone-aware")

    config = residual_v12_paper_config()
    ledger = Ledger(ledger_path)
    session = PaperTradingSession(ledger, config)
    try:
        existing_exposures = _existing_exposures(ledger)
        existing_day_stakes: dict[str, int] = {}
        for exposure in existing_exposures:
            scheduled = exposure["scheduled_post_time"]
            day_key = scheduled.date().isoformat()
            stake = int(exposure["stake_yen"])
            existing_day_stakes[day_key] = (
                existing_day_stakes.get(day_key, 0) + stake
            )
            session.seed_exposure(
                scheduled_post_time=scheduled,
                race_id=exposure["race_id"],
                stake_yen=stake,
                bankroll_yen=bankroll_yen,
            )

        frame = predictions.copy()
        frame["observed_at"] = pd.to_datetime(
            frame["observed_at"],
            errors="raise",
            utc=True,
        )
        frame["scheduled_post_time"] = pd.to_datetime(
            frame["scheduled_post_time"],
            errors="raise",
            utc=True,
        )
        frame = frame.sort_values(
            ["scheduled_post_time", "race_id", "post_position"],
            kind="stable",
        )

        counters = {
            "eligible_rows": 0,
            "past_or_not_yet_observed_rows": 0,
            "duplicate_evaluations": 0,
            "new_evaluations": 0,
            "new_selected_bets": 0,
            "new_committed_stake_yen": 0,
        }
        available_by_day: dict[str, int] = {}

        for row in frame.itertuples(index=False):
            observed_at = _aware_datetime(
                row.observed_at,
                "observed_at",
            )
            scheduled_post_time = _aware_datetime(
                row.scheduled_post_time,
                "scheduled_post_time",
            )
            if not (
                observed_at <= decision_time < scheduled_post_time
            ):
                counters["past_or_not_yet_observed_rows"] += 1
                continue

            counters["eligible_rows"] += 1
            race_id = str(row.race_id)
            horse_id = str(row.horse_id)
            source = str(
                getattr(row, "source", "") or "JRA-VAN 0B31"
            )
            source_reference = str(
                getattr(row, "source_reference", "") or ""
            )
            probability = float(row.residual_v12_probability)
            decimal_odds = float(row.decimal_odds)

            existing = _existing_prediction_for_snapshot(
                ledger,
                race_id=race_id,
                horse_id=horse_id,
                observed_at=observed_at,
                source=source,
            )
            if existing is not None:
                _, prior_probability, prior_odds = existing
                if (
                    abs(prior_probability - probability) > 1e-12
                    or abs(prior_odds - decimal_odds) > 1e-12
                ):
                    raise ValueError(
                        "immutable Residual v12 Paper prediction conflict"
                    )
                counters["duplicate_evaluations"] += 1
                continue

            snapshot = PreRaceOddsSnapshot(
                race_id=race_id,
                horse_id=horse_id,
                horse_name=str(row.horse_name),
                decimal_odds=decimal_odds,
                observed_at=observed_at,
                scheduled_post_time=scheduled_post_time,
                source=source,
                source_reference=source_reference,
            )
            prediction = HorsePrediction(
                race_id=race_id,
                horse_id=horse_id,
                horse_name=str(row.horse_name),
                predicted_win_probability=probability,
                decimal_odds=decimal_odds,
                confidence=0.0,
                model_version=PAPER_MODEL_VERSION,
                predicted_at=decision_time,
                metadata={
                    "paper_policy_version": PAPER_POLICY_VERSION,
                    "confidence_gate": "disabled_no_separate_v12_confidence",
                },
            )

            day_key = scheduled_post_time.date().isoformat()
            if day_key not in available_by_day:
                available_by_day[day_key] = max(
                    0,
                    int(bankroll_yen)
                    - int(existing_day_stakes.get(day_key, 0)),
                )
            available = available_by_day[day_key]
            if available <= 0:
                evaluation_bankroll = int(bankroll_yen)
            else:
                evaluation_bankroll = available

            result = session.evaluate(
                prediction,
                snapshot,
                bankroll_yen=evaluation_bankroll,
            )
            counters["new_evaluations"] += 1

            if result.receipt.accepted:
                stake = int(result.decision.stake_yen)
                counters["new_selected_bets"] += 1
                counters["new_committed_stake_yen"] += stake
                available_by_day[day_key] = max(0, available - stake)

        performance = summarize_residual_v12_paper(ledger)
        return {
            "status": (
                "prospective_evaluations_recorded"
                if counters["new_evaluations"] > 0
                else (
                    "already_recorded"
                    if counters["duplicate_evaluations"] > 0
                    else "no_eligible_future_predictions"
                )
            ),
            "policy_version": PAPER_POLICY_VERSION,
            "model_version": PAPER_MODEL_VERSION,
            "fixed_gamma": float(FIXED_GAMMA),
            "min_ev": float(PAPER_MIN_EV),
            "min_probability": float(PAPER_MIN_PROBABILITY),
            "confidence_gate_enabled": False,
            "fractional_kelly": float(PAPER_FRACTIONAL_KELLY),
            "max_race_fraction": float(PAPER_MAX_RACE_FRACTION),
            "max_day_fraction": float(PAPER_MAX_DAY_FRACTION),
            "bankroll_yen": int(bankroll_yen),
            **counters,
            "performance": performance,
            "prospective_only": True,
            "historical_forward_rows_backfilled": False,
            "live_execution_enabled": False,
        }
    finally:
        ledger.close()
