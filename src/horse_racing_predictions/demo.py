from datetime import datetime
from pathlib import Path
from .config import DEFAULT_CONFIG
from .domain import HorsePrediction
from .strategy import decide_win_bet
from .broker import PaperBroker
from .ledger import Ledger

def main():
    db = Path("demo_racing.sqlite3")
    if db.exists():
        db.unlink()
    ledger = Ledger(db)
    broker = PaperBroker()
    bankroll = 100_000

    predictions = [
        HorsePrediction("2026-DEMO-01","H01","Alpha",0.22,6.2,0.74,"baseline-v0",datetime.now()),
        HorsePrediction("2026-DEMO-01","H02","Bravo",0.35,2.1,0.80,"baseline-v0",datetime.now()),
        HorsePrediction("2026-DEMO-02","H03","Charlie",0.09,15.0,0.63,"baseline-v0",datetime.now()),
    ]

    for p in predictions:
        ledger.record_prediction(p)
        d = decide_win_bet(p, bankroll, DEFAULT_CONFIG)
        print(p.horse_name, f"EV={p.expected_return_multiple:.3f}", d.reason, d.stake_yen)
        if d.stake_yen:
            print(broker.place(d))
            ledger.record_bet(d)

    print("summary:", ledger.summary())
    ledger.close()

if __name__ == "__main__":
    main()
