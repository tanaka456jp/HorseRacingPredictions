from datetime import datetime, timedelta, timezone

from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.ledger import Ledger
from horse_racing_predictions.paper_session import PaperTradingSession
from horse_racing_predictions.snapshots import PreRaceOddsSnapshot


UTC = timezone.utc


def _case(race_id, horse_id, post, odds=4.0):
    observed = post - timedelta(minutes=10)
    snapshot = PreRaceOddsSnapshot(
        race_id=race_id,
        horse_id=horse_id,
        horse_name=horse_id,
        decimal_odds=odds,
        observed_at=observed,
        scheduled_post_time=post,
        source="risk-test",
        source_reference=f"{race_id}-{horse_id}",
    )
    prediction = HorsePrediction(
        race_id=race_id,
        horse_id=horse_id,
        horse_name=horse_id,
        predicted_win_probability=0.50,
        decimal_odds=odds,
        confidence=1.0,
        model_version="risk-v1",
        predicted_at=observed + timedelta(minutes=1),
    )
    return prediction, snapshot


def _config():
    return StrategyConfig(
        min_ev=1.05,
        min_probability=0.01,
        min_confidence=0.0,
        fractional_kelly=1.0,
        max_race_fraction=0.02,
        max_day_fraction=0.05,
        max_bet_yen=100_000,
        min_bet_yen=100,
        bet_unit_yen=100,
    )


def test_race_exposure_cap_is_shared_across_horses(tmp_path):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    session = PaperTradingSession(ledger, _config())
    post = datetime(2026, 10, 11, 6, 30, tzinfo=UTC)

    first = session.evaluate(
        *_case("R1", "H1", post),
        bankroll_yen=100_000,
    )
    second = session.evaluate(
        *_case("R1", "H2", post),
        bankroll_yen=100_000,
    )

    assert first.decision.stake_yen == 2_000
    assert second.decision.stake_yen == 0
    assert second.decision.reason == "race_or_day_budget_exhausted"

    exposure = session.exposure_snapshot()
    assert exposure["race_stakes"][("2026-10-11", "R1")] == 2_000
    ledger.close()


def test_day_exposure_cap_is_shared_across_races(tmp_path):
    ledger = Ledger(tmp_path / "paper.sqlite3")
    session = PaperTradingSession(ledger, _config())
    base = datetime(2026, 10, 11, 5, 30, tzinfo=UTC)

    results = []
    for index in range(1, 5):
        prediction, snapshot = _case(
            f"R{index}",
            f"H{index}",
            base + timedelta(minutes=index * 30),
        )
        results.append(
            session.evaluate(
                prediction,
                snapshot,
                bankroll_yen=100_000,
            )
        )

    stakes = [result.decision.stake_yen for result in results]
    assert stakes == [2_000, 2_000, 1_000, 0]
    assert sum(stakes) == 5_000

    exposure = session.exposure_snapshot()
    assert exposure["day_stakes"]["2026-10-11"] == 5_000
    assert exposure["day_limits"]["2026-10-11"] == 5_000
    ledger.close()
