from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.paper_session import PaperTradingSession
from horse_racing_predictions.paper_settlement import (
    settle_paper_bets_from_history,
)
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc
RACE_ID = "20260927-08-03-04-11"


def _paper_bet(tmp_path, *, post_position=1):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    post = datetime(2026, 9, 27, 6, 30, tzinfo=UTC)
    observed = post - timedelta(minutes=30)
    horse_id = f"{RACE_ID}-{post_position}"
    snapshot = PreRaceOddsSnapshot(
        race_id=RACE_ID,
        horse_id=horse_id,
        horse_name="ALPHA",
        decimal_odds=4.0,
        observed_at=observed,
        scheduled_post_time=post,
        source="JRA-VAN 0B31",
        source_reference="quote-1",
    )
    prediction = HorsePrediction(
        race_id=RACE_ID,
        horse_id=horse_id,
        horse_name="ALPHA",
        predicted_win_probability=0.50,
        decimal_odds=4.0,
        confidence=0.90,
        model_version="champion-v7",
        predicted_at=observed + timedelta(minutes=1),
    )
    session = PaperTradingSession(
        ledger,
        StrategyConfig(
            min_ev=1.05,
            min_probability=0.01,
            min_confidence=0.50,
            fractional_kelly=0.25,
            max_race_fraction=0.05,
            max_day_fraction=0.10,
        ),
    )
    result = session.evaluate(
        prediction,
        snapshot,
        bankroll_yen=100_000,
    )
    assert result.bet_id is not None
    return ledger, result.bet_id, result.decision.stake_yen


def _history(*, horse1_finish=1, horse2_finish=2, horse1_odds=3.2):
    return pd.DataFrame([
        {
            "race_id": RACE_ID,
            "post_position": 1,
            "finish_position": horse1_finish,
            "win_odds": horse1_odds,
        },
        {
            "race_id": RACE_ID,
            "post_position": 2,
            "finish_position": horse2_finish,
            "win_odds": 5.5,
        },
    ])


def test_settlement_records_win_with_final_odds(tmp_path):
    ledger, bet_id, stake = _paper_bet(tmp_path, post_position=1)

    summary = settle_paper_bets_from_history(
        ledger=ledger,
        history=_history(),
        source="test-final",
        source_reference="fixture.csv",
    )

    assert summary.settled_now == 1
    assert summary.wins == 1
    assert summary.losses == 0
    assert summary.unsettled_after == 0
    assert summary.payout_yen == round(stake * 3.2)

    row = ledger.conn.execute(
        "SELECT result,payout_yen FROM bets WHERE id=?",
        (bet_id,),
    ).fetchone()
    assert row == ("WIN", round(stake * 3.2))

    evidence = ledger.conn.execute(
        "SELECT finish_position,final_win_odds,result,payout_yen,source "
        "FROM paper_settlement_evidence WHERE bet_id=?",
        (bet_id,),
    ).fetchone()
    assert evidence == (
        1,
        3.2,
        "WIN",
        round(stake * 3.2),
        "test-final",
    )
    ledger.close()


def test_settlement_records_loss_with_zero_payout(tmp_path):
    ledger, bet_id, _stake = _paper_bet(tmp_path, post_position=2)

    summary = settle_paper_bets_from_history(
        ledger=ledger,
        history=_history(),
        source="test-final",
    )

    assert summary.settled_now == 1
    assert summary.losses == 1
    assert summary.payout_yen == 0
    row = ledger.conn.execute(
        "SELECT result,payout_yen FROM bets WHERE id=?",
        (bet_id,),
    ).fetchone()
    assert row == ("LOSE", 0)
    ledger.close()


def test_settlement_fails_closed_on_multiple_winners(tmp_path):
    ledger, bet_id, _stake = _paper_bet(tmp_path, post_position=1)

    summary = settle_paper_bets_from_history(
        ledger=ledger,
        history=_history(
            horse1_finish=1,
            horse2_finish=1,
        ),
        source="test-final",
    )

    assert summary.settled_now == 0
    assert summary.pending_invalid_race_result == 1
    assert summary.unsettled_after == 1
    row = ledger.conn.execute(
        "SELECT result FROM bets WHERE id=?",
        (bet_id,),
    ).fetchone()
    assert row == (None,)
    ledger.close()


def test_settlement_is_idempotent(tmp_path):
    ledger, bet_id, _stake = _paper_bet(tmp_path, post_position=1)

    first = settle_paper_bets_from_history(
        ledger=ledger,
        history=_history(),
        source="test-final",
        source_reference="fixture.csv",
    )
    second = settle_paper_bets_from_history(
        ledger=ledger,
        history=_history(),
        source="test-final",
        source_reference="fixture.csv",
    )

    assert first.settled_now == 1
    assert second.unsettled_before == 0
    assert second.settled_now == 0
    evidence_count = ledger.conn.execute(
        "SELECT COUNT(*) FROM paper_settlement_evidence WHERE bet_id=?",
        (bet_id,),
    ).fetchone()[0]
    assert evidence_count == 1
    ledger.close()


def test_settlement_rejects_conflicting_replay(tmp_path):
    ledger, bet_id, stake = _paper_bet(tmp_path, post_position=1)
    created = ledger.record_paper_settlement(
        bet_id=bet_id,
        race_id=RACE_ID,
        horse_id=f"{RACE_ID}-1",
        finish_position=1,
        final_win_odds=3.2,
        won=True,
        payout_yen=round(stake * 3.2),
        source="test-final",
        source_reference="fixture.csv",
    )
    assert created is True

    with pytest.raises(ValueError, match="immutable settlement evidence conflict"):
        ledger.record_paper_settlement(
            bet_id=bet_id,
            race_id=RACE_ID,
            horse_id=f"{RACE_ID}-1",
            finish_position=1,
            final_win_odds=3.3,
            won=True,
            payout_yen=round(stake * 3.3),
            source="test-final",
            source_reference="fixture.csv",
        )
    ledger.close()
