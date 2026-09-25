from datetime import datetime, timedelta, timezone

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.paper_session import PaperTradingSession
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc


def _case(probability=0.30, odds=5.0, confidence=0.90):
    post = datetime(2026, 10, 4, 6, 30, tzinfo=UTC)
    observed = post - timedelta(minutes=10)

    snapshot = PreRaceOddsSnapshot(
        race_id="RACE-1",
        horse_id="H1",
        horse_name="ALPHA",
        decimal_odds=odds,
        observed_at=observed,
        scheduled_post_time=post,
        source="paper-provider",
        source_reference="quote-1",
    )
    prediction = HorsePrediction(
        race_id="RACE-1",
        horse_id="H1",
        horse_name="ALPHA",
        predicted_win_probability=probability,
        decimal_odds=odds,
        confidence=confidence,
        model_version="paper-model-v1",
        predicted_at=observed + timedelta(minutes=1),
    )
    return prediction, snapshot


def test_selected_paper_bet_links_to_prediction_evidence(tmp_path):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    prediction, snapshot = _case()

    session = PaperTradingSession(
        ledger,
        StrategyConfig(
            min_ev=1.10,
            min_probability=0.01,
            min_confidence=0.50,
        ),
    )
    result = session.evaluate(
        prediction,
        snapshot,
        bankroll_yen=100_000,
    )

    assert result.prediction_id > 0
    assert result.decision.stake_yen > 0
    assert result.receipt.accepted
    assert result.bet_id is not None

    evidence = ledger.paper_bet_evidence(result.bet_id)
    assert evidence["prediction_id"] == result.prediction_id
    assert evidence["race_id"] == prediction.race_id
    assert evidence["horse_id"] == prediction.horse_id
    assert evidence["decimal_odds"] == prediction.decimal_odds
    assert evidence["broker_reference"] == result.receipt.reference
    ledger.close()


def test_no_bet_still_records_prediction_but_not_bet(tmp_path):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    prediction, snapshot = _case(
        probability=0.10,
        odds=2.0,
        confidence=0.90,
    )

    session = PaperTradingSession(
        ledger,
        StrategyConfig(
            min_ev=1.10,
            min_probability=0.01,
            min_confidence=0.50,
        ),
    )
    result = session.evaluate(
        prediction,
        snapshot,
        bankroll_yen=100_000,
    )

    assert result.prediction_id > 0
    assert result.decision.stake_yen == 0
    assert not result.receipt.accepted
    assert result.bet_id is None

    prediction_count = ledger.conn.execute(
        "SELECT COUNT(*) FROM predictions"
    ).fetchone()[0]
    bet_count = ledger.conn.execute(
        "SELECT COUNT(*) FROM bets"
    ).fetchone()[0]
    assert prediction_count == 1
    assert bet_count == 0
    ledger.close()
