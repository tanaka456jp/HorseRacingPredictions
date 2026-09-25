from datetime import datetime
from horse_racing_predictions.config import StrategyConfig
from horse_racing_predictions.domain import HorsePrediction
from horse_racing_predictions.staking import kelly_fraction, rounded_stake
from horse_racing_predictions.strategy import decide_win_bet
from horse_racing_predictions.ledger import Ledger

def test_ev_and_fair_odds():
    p = HorsePrediction("R","H","Horse",0.20,8.0,0.8,"v",datetime.now())
    assert round(p.expected_return_multiple,6) == 1.6
    assert round(p.fair_odds,6) == 5.0
    assert round(p.edge,6) == 0.6

def test_kelly_positive_and_capped():
    assert kelly_fraction(0.20,8.0) > 0
    stake = rounded_stake(100_000,0.20,8.0,0.25,0.02,10_000,100,100)
    assert 0 < stake <= 2_000
    assert stake % 100 == 0

def test_low_ev_is_not_bought():
    p = HorsePrediction("R","H","Horse",0.50,1.8,0.9,"v",datetime.now())
    d = decide_win_bet(p,100_000,StrategyConfig(min_ev=1.15))
    assert d.stake_yen == 0
    assert d.reason == "ev_below_threshold"

def test_ledger_roundtrip(tmp_path):
    ledger = Ledger(tmp_path/"x.sqlite3")
    p = HorsePrediction("R","H","Horse",0.20,8.0,0.8,"v",datetime.now())
    ledger.record_prediction(p)
    d = decide_win_bet(p,100_000,StrategyConfig())
    bid = ledger.record_bet(d)
    ledger.settle_bet(bid, True, int(d.stake_yen*8.0))
    s = ledger.summary()
    assert s["bets"] == 1
    assert s["payout_yen"] > s["stake_yen"]
    ledger.close()
