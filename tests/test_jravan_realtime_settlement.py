from datetime import datetime, timedelta, timezone

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.jravan import JvRawRecord
from horse_racing_predictions.jravan_realtime_settlement import (
    realtime_result_key_from_race_id,
    run_realtime_paper_settlement,
)
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.paper_session import PaperTradingSession
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc
RACE_ID = "20260927-08-03-04-11"


def _put(buffer, position, length, value, encoding="ascii"):
    raw = str(value).encode(encoding)
    assert len(raw) <= length
    start = position - 1
    buffer[start:start + length] = (
        raw + b" " * (length - len(raw))
    )


def _ra(data_division="7"):
    buffer = bytearray(b" " * 1270)
    _put(buffer, 1, 2, "RA")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0927")
    _put(buffer, 20, 2, "08")
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 615, 1, "A")
    _put(buffer, 635, 3, "999")
    _put(buffer, 698, 4, "1600")
    _put(buffer, 706, 2, "17")
    _put(buffer, 888, 1, "1")
    _put(buffer, 889, 1, "1")
    _put(buffer, 890, 1, "2")
    return bytes(buffer).decode("cp932")


def _se(
    post_position,
    horse_name,
    *,
    blood_no,
    finish_position,
    win_odds_tenths,
    data_division="7",
):
    buffer = bytearray(b" " * 553)
    _put(buffer, 1, 2, "SE")
    _put(buffer, 3, 1, data_division)
    _put(buffer, 12, 4, "2026")
    _put(buffer, 16, 4, "0927")
    _put(buffer, 20, 2, "08")
    _put(buffer, 22, 2, "03")
    _put(buffer, 24, 2, "04")
    _put(buffer, 26, 2, "11")
    _put(buffer, 29, 2, f"{post_position:02d}")
    _put(buffer, 31, 10, blood_no)
    _put(buffer, 41, 36, horse_name, "cp932")
    _put(buffer, 79, 1, "1")
    _put(buffer, 83, 2, "03")
    _put(buffer, 91, 8, "調教A", "cp932")
    _put(buffer, 289, 3, "570")
    _put(buffer, 307, 8, "騎手A", "cp932")
    _put(buffer, 332, 1, "0")
    _put(buffer, 335, 2, f"{finish_position:02d}")
    _put(buffer, 360, 4, f"{win_odds_tenths:04d}")
    _put(buffer, 364, 2, f"{post_position:02d}")
    return bytes(buffer).decode("cp932")


class FakeResultClient:
    instances = []

    def __init__(self, records):
        self.records = list(records)
        self.initialized = False
        self.opened = False
        self.open_args = None
        type(self).instances.append(self)

    def initialize(self):
        self.initialized = True

    def open_realtime(self, *, dataspec, key):
        self.open_args = (dataspec, key)
        self.opened = True
        return 0

    def iter_records(self):
        yield from self.records

    def close(self):
        self.opened = False


def _accepted_paper_bet(tmp_path):
    ledger_path = tmp_path / "paper.sqlite3"
    ledger = Ledger(ledger_path)
    post = datetime(2026, 9, 27, 1, 30, tzinfo=UTC)
    observed = post - timedelta(minutes=20)
    snapshot = PreRaceOddsSnapshot(
        race_id=RACE_ID,
        horse_id=f"{RACE_ID}-1",
        horse_name="アルファ",
        decimal_odds=4.0,
        observed_at=observed,
        scheduled_post_time=post,
        source="JRA-VAN 0B31",
        source_reference="quote-1",
    )
    prediction = HorsePrediction(
        race_id=RACE_ID,
        horse_id=f"{RACE_ID}-1",
        horse_name="アルファ",
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
        ),
    )
    result = session.evaluate(
        prediction,
        snapshot,
        bankroll_yen=100_000,
    )
    assert result.bet_id is not None
    stake = result.decision.stake_yen
    ledger.close()
    return ledger_path, result.bet_id, stake


def test_realtime_result_key_uses_date_course_and_race():
    assert (
        realtime_result_key_from_race_id(RACE_ID)
        == "202609270811"
    )


def test_no_unsettled_bets_does_not_open_jvlink(tmp_path):
    ledger_path = tmp_path / "paper.sqlite3"
    ledger = Ledger(ledger_path)
    ledger.close()

    def should_not_be_called():
        raise AssertionError("JV-Link should not be opened")

    summary = run_realtime_paper_settlement(
        ledger_path=ledger_path,
        client_factory=should_not_be_called,
    )

    assert summary.status == "no_unsettled_bets"
    assert summary.races_requested == 0
    assert summary.settled_now == 0


def test_realtime_0b12_settles_completed_win(tmp_path):
    ledger_path, bet_id, stake = _accepted_paper_bet(tmp_path)
    records = [
        JvRawRecord("RA", _ra()),
        JvRawRecord(
            "SE",
            _se(
                1,
                "アルファ",
                blood_no="2023100001",
                finish_position=1,
                win_odds_tenths=32,
            ),
        ),
        JvRawRecord(
            "SE",
            _se(
                2,
                "ブラボー",
                blood_no="2023100002",
                finish_position=2,
                win_odds_tenths=55,
            ),
        ),
    ]
    FakeResultClient.instances.clear()

    summary = run_realtime_paper_settlement(
        ledger_path=ledger_path,
        client_factory=lambda: FakeResultClient(records),
    )

    assert summary.status == "settled"
    assert summary.races_requested == 1
    assert summary.races_completed == 1
    assert summary.settled_now == 1
    assert summary.wins == 1
    assert summary.payout_yen == round(stake * 3.2)
    assert (
        FakeResultClient.instances[0].open_args
        == ("0B12", "202609270811")
    )

    ledger = Ledger(ledger_path)
    row = ledger.conn.execute(
        "SELECT result,payout_yen FROM bets WHERE id=?",
        (bet_id,),
    ).fetchone()
    assert row == ("WIN", round(stake * 3.2))
    ledger.close()


def test_incomplete_realtime_result_stays_pending(tmp_path):
    ledger_path, bet_id, _stake = _accepted_paper_bet(tmp_path)
    records = [
        JvRawRecord("RA", _ra()),
    ]

    summary = run_realtime_paper_settlement(
        ledger_path=ledger_path,
        client_factory=lambda: FakeResultClient(records),
    )

    assert summary.status == "pending_results"
    assert summary.races_completed == 0
    assert summary.settled_now == 0
    assert summary.unsettled_after == 1

    ledger = Ledger(ledger_path)
    row = ledger.conn.execute(
        "SELECT result FROM bets WHERE id=?",
        (bet_id,),
    ).fetchone()
    assert row == (None,)
    ledger.close()
