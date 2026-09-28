from datetime import datetime, timedelta, timezone

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.paper_session import PaperTradingSession
from horse_racing_predictions.residual_paper_evidence import (
    MIN_PROSPECTIVE_EVALUATED_RACES,
    MIN_SETTLED_PAPER_BETS,
    build_residual_v12_paper_evidence_report,
)
from horse_racing_predictions.residual_shadow_paper import (
    PAPER_MODEL_VERSION,
)
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc


def _insert_evaluation(
    ledger,
    *,
    race_id,
    stake_yen=0,
    won=False,
):
    observed = datetime(2026, 9, 29, 0, 0, tzinfo=UTC)
    post = observed + timedelta(hours=1)
    horse_id = f"{race_id}-1"
    snapshot = PreRaceOddsSnapshot(
        race_id=race_id,
        horse_id=horse_id,
        horse_name="ALPHA",
        decimal_odds=4.0,
        observed_at=observed,
        scheduled_post_time=post,
        source="test",
        source_reference=race_id,
    )
    prediction = HorsePrediction(
        race_id=race_id,
        horse_id=horse_id,
        horse_name="ALPHA",
        predicted_win_probability=0.40,
        decimal_odds=4.0,
        confidence=0.0,
        model_version=PAPER_MODEL_VERSION,
        predicted_at=observed + timedelta(minutes=1),
    )
    prediction_id = ledger.record_paper_prediction(
        prediction,
        snapshot,
    )
    if stake_yen <= 0:
        return

    from horse_racing_predictions.domain import BetDecision

    decision = BetDecision(
        race_id=race_id,
        horse_id=horse_id,
        horse_name="ALPHA",
        bet_type="WIN",
        stake_yen=stake_yen,
        decimal_odds=4.0,
        expected_return_multiple=1.6,
        edge=0.6,
        reason="selected",
        model_version=PAPER_MODEL_VERSION,
    )
    bet_id = ledger.record_paper_bet(
        decision,
        prediction_id,
        broker="paper",
        broker_reference=race_id,
    )
    ledger.record_paper_settlement(
        bet_id=bet_id,
        race_id=race_id,
        horse_id=horse_id,
        finish_position=1 if won else 2,
        final_win_odds=4.0 if won else None,
        won=won,
        payout_yen=stake_yen * 4 if won else 0,
        source="test-final",
    )


def test_evidence_gate_stays_closed_below_frozen_thresholds(tmp_path):
    ledger_path = tmp_path / "paper.sqlite3"
    ledger = Ledger(ledger_path)
    try:
        for index in range(3):
            _insert_evaluation(
                ledger,
                race_id=f"R{index}",
                stake_yen=100,
                won=index == 0,
            )
    finally:
        ledger.close()

    report = build_residual_v12_paper_evidence_report(ledger_path)

    assert report["status"] == "insufficient_evidence"
    assert report["prospective_evaluated_races"] == 3
    assert report["settled_paper_bets"] == 3
    assert report["sufficient_evidence"] is False
    assert report["minimum_prospective_evaluated_races"] == 500
    assert report["minimum_settled_paper_bets"] == 200
    assert report["automatic_live_promotion"] is False
    assert report["live_execution_enabled"] is False


def test_evidence_gate_reports_positive_roi_only_after_sample_gate(tmp_path):
    ledger_path = tmp_path / "paper.sqlite3"
    ledger = Ledger(ledger_path)
    try:
        # Insert directly at scale to keep the test fast while preserving
        # the same model-version/evidence relationships queried by the gate.
        for index in range(MIN_PROSPECTIVE_EVALUATED_RACES):
            race_id = f"R{index:04d}"
            horse_id = f"{race_id}-1"
            cur = ledger.conn.execute(
                """
                INSERT INTO predictions (
                    race_id,horse_id,horse_name,predicted_win_probability,
                    decimal_odds,confidence,expected_return_multiple,edge,
                    model_version,predicted_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    race_id,horse_id,"ALPHA",0.40,4.0,0.0,1.6,0.6,
                    PAPER_MODEL_VERSION,
                    "2026-09-29T00:01:00+00:00",
                ),
            )
            prediction_id = int(cur.lastrowid)
            snap = ledger.conn.execute(
                """
                INSERT INTO pre_race_odds_snapshots (
                    race_id,horse_id,horse_name,decimal_odds,observed_at,
                    scheduled_post_time,source,source_reference
                ) VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    race_id,horse_id,"ALPHA",4.0,
                    "2026-09-29T00:00:00+00:00",
                    "2026-09-29T01:00:00+00:00",
                    "test",race_id,
                ),
            )
            snapshot_id = int(snap.lastrowid)
            ledger.conn.execute(
                """
                INSERT INTO paper_prediction_evidence (
                    prediction_id,odds_snapshot_id,recorded_at
                ) VALUES (?,?,?)
                """,
                (
                    prediction_id,snapshot_id,
                    "2026-09-29T00:01:00+00:00",
                ),
            )
            if index < MIN_SETTLED_PAPER_BETS:
                won = index % 3 == 0
                bet = ledger.conn.execute(
                    """
                    INSERT INTO bets (
                        race_id,horse_id,horse_name,bet_type,stake_yen,
                        decimal_odds,expected_return_multiple,edge,reason,
                        model_version,placed_at,result,payout_yen
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        race_id,horse_id,"ALPHA","WIN",100,4.0,1.6,0.6,
                        "selected",PAPER_MODEL_VERSION,
                        "2026-09-29T00:01:00+00:00",
                        "WIN" if won else "LOSE",
                        400 if won else 0,
                    ),
                )
                bet_id = int(bet.lastrowid)
                ledger.conn.execute(
                    """
                    INSERT INTO paper_bet_evidence (
                        bet_id,prediction_id,broker,broker_reference,recorded_at
                    ) VALUES (?,?,?,?,?)
                    """,
                    (
                        bet_id,prediction_id,"paper",race_id,
                        "2026-09-29T00:01:00+00:00",
                    ),
                )
        ledger.conn.commit()
    finally:
        ledger.close()

    report = build_residual_v12_paper_evidence_report(ledger_path)

    assert report["prospective_evaluated_races"] == 500
    assert report["settled_paper_bets"] == 200
    assert report["sufficient_evidence"] is True
    assert report["observed_positive_roi"] is True
    assert report["status"] == "review_ready_positive_observed_roi"
    assert report["automatic_live_promotion"] is False
