import sqlite3
from datetime import datetime

SCHEMA = (
"CREATE TABLE IF NOT EXISTS predictions("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"race_id TEXT NOT NULL,horse_id TEXT NOT NULL,horse_name TEXT NOT NULL,"
"predicted_win_probability REAL NOT NULL,decimal_odds REAL NOT NULL,"
"confidence REAL NOT NULL,expected_return_multiple REAL NOT NULL,"
"edge REAL NOT NULL,model_version TEXT NOT NULL,predicted_at TEXT NOT NULL);"
"CREATE TABLE IF NOT EXISTS bets("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"race_id TEXT NOT NULL,horse_id TEXT NOT NULL,horse_name TEXT NOT NULL,"
"bet_type TEXT NOT NULL,stake_yen INTEGER NOT NULL,decimal_odds REAL NOT NULL,"
"expected_return_multiple REAL NOT NULL,edge REAL NOT NULL,reason TEXT NOT NULL,"
"model_version TEXT NOT NULL,placed_at TEXT NOT NULL,result TEXT,"
"payout_yen INTEGER DEFAULT 0);"
)

class Ledger:
    def __init__(self, path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record_prediction(self, p):
        self.conn.execute(
            "INSERT INTO predictions "
            "(race_id,horse_id,horse_name,predicted_win_probability,decimal_odds,"
            "confidence,expected_return_multiple,edge,model_version,predicted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p.race_id,p.horse_id,p.horse_name,p.predicted_win_probability,
             p.decimal_odds,p.confidence,p.expected_return_multiple,p.edge,
             p.model_version,p.predicted_at.isoformat())
        )
        self.conn.commit()

    def record_bet(self, d):
        cur = self.conn.execute(
            "INSERT INTO bets "
            "(race_id,horse_id,horse_name,bet_type,stake_yen,decimal_odds,"
            "expected_return_multiple,edge,reason,model_version,placed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (d.race_id,d.horse_id,d.horse_name,d.bet_type,d.stake_yen,d.decimal_odds,
             d.expected_return_multiple,d.edge,d.reason,d.model_version,
             datetime.now().isoformat())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def settle_bet(self, bet_id, won, payout_yen):
        self.conn.execute(
            "UPDATE bets SET result=?, payout_yen=? WHERE id=?",
            ("WIN" if won else "LOSE", int(payout_yen), bet_id)
        )
        self.conn.commit()

    def summary(self):
        row = self.conn.execute(
            "SELECT COUNT(*),COALESCE(SUM(stake_yen),0),COALESCE(SUM(payout_yen),0) "
            "FROM bets WHERE stake_yen > 0"
        ).fetchone()
        count, stake, payout = row
        profit = payout - stake
        roi = (payout / stake - 1.0) if stake else 0.0
        return {"bets":count,"stake_yen":stake,"payout_yen":payout,
                "profit_yen":profit,"roi":roi}

    def close(self):
        self.conn.close()
