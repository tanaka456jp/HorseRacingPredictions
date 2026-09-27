import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from .snapshots import validate_prediction_evidence

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
"CREATE TABLE IF NOT EXISTS pre_race_odds_snapshots("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"race_id TEXT NOT NULL,horse_id TEXT NOT NULL,horse_name TEXT NOT NULL,"
"decimal_odds REAL NOT NULL,observed_at TEXT NOT NULL,"
"scheduled_post_time TEXT NOT NULL,source TEXT NOT NULL,"
"source_reference TEXT NOT NULL DEFAULT '',"
"UNIQUE(race_id,horse_id,observed_at,source));"
"CREATE TABLE IF NOT EXISTS paper_prediction_evidence("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"prediction_id INTEGER NOT NULL UNIQUE,"
"odds_snapshot_id INTEGER NOT NULL,"
"recorded_at TEXT NOT NULL,"
"FOREIGN KEY(prediction_id) REFERENCES predictions(id),"
"FOREIGN KEY(odds_snapshot_id) REFERENCES pre_race_odds_snapshots(id));"
"CREATE TABLE IF NOT EXISTS paper_bet_evidence("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"bet_id INTEGER NOT NULL UNIQUE,"
"prediction_id INTEGER NOT NULL,"
"broker TEXT NOT NULL,broker_reference TEXT NOT NULL,"
"recorded_at TEXT NOT NULL,"
"FOREIGN KEY(bet_id) REFERENCES bets(id),"
"FOREIGN KEY(prediction_id) REFERENCES predictions(id));"
"CREATE TABLE IF NOT EXISTS paper_settlement_evidence("
"id INTEGER PRIMARY KEY AUTOINCREMENT,"
"bet_id INTEGER NOT NULL UNIQUE,"
"race_id TEXT NOT NULL,horse_id TEXT NOT NULL,"
"finish_position INTEGER NOT NULL,final_win_odds REAL,"
"result TEXT NOT NULL,payout_yen INTEGER NOT NULL,"
"source TEXT NOT NULL,source_reference TEXT NOT NULL DEFAULT '',"
"recorded_at TEXT NOT NULL,"
"FOREIGN KEY(bet_id) REFERENCES bets(id));"
)

class Ledger:
    def __init__(self, path):
        self.path = str(path)
        if self.path != ":memory:":
            parent = Path(self.path).parent
            if parent != Path("."):
                parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def record_prediction(self, p):
        cur = self.conn.execute(
            "INSERT INTO predictions "
            "(race_id,horse_id,horse_name,predicted_win_probability,decimal_odds,"
            "confidence,expected_return_multiple,edge,model_version,predicted_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (p.race_id,p.horse_id,p.horse_name,p.predicted_win_probability,
             p.decimal_odds,p.confidence,p.expected_return_multiple,p.edge,
             p.model_version,p.predicted_at.isoformat())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def record_pre_race_snapshot(self, snapshot):
        existing = self.conn.execute(
            "SELECT id,horse_name,decimal_odds,scheduled_post_time,source_reference "
            "FROM pre_race_odds_snapshots "
            "WHERE race_id=? AND horse_id=? AND observed_at=? AND source=?",
            (
                snapshot.race_id,
                snapshot.horse_id,
                snapshot.observed_at.isoformat(),
                snapshot.source,
            ),
        ).fetchone()

        expected = (
            snapshot.horse_name,
            float(snapshot.decimal_odds),
            snapshot.scheduled_post_time.isoformat(),
            snapshot.source_reference,
        )
        if existing is not None:
            actual = (
                existing[1],
                float(existing[2]),
                existing[3],
                existing[4],
            )
            if actual != expected:
                raise ValueError(
                    "immutable odds snapshot conflict for the same observation key"
                )
            return int(existing[0])

        cur = self.conn.execute(
            "INSERT INTO pre_race_odds_snapshots "
            "(race_id,horse_id,horse_name,decimal_odds,observed_at,"
            "scheduled_post_time,source,source_reference) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                snapshot.race_id,
                snapshot.horse_id,
                snapshot.horse_name,
                float(snapshot.decimal_odds),
                snapshot.observed_at.isoformat(),
                snapshot.scheduled_post_time.isoformat(),
                snapshot.source,
                snapshot.source_reference,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def record_paper_prediction(self, prediction, snapshot):
        validate_prediction_evidence(prediction, snapshot)
        snapshot_id = self.record_pre_race_snapshot(snapshot)
        prediction_id = self.record_prediction(prediction)
        self.conn.execute(
            "INSERT INTO paper_prediction_evidence "
            "(prediction_id,odds_snapshot_id,recorded_at) VALUES (?,?,?)",
            (
                prediction_id,
                snapshot_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        return prediction_id

    def paper_evidence(self, prediction_id):
        row = self.conn.execute(
            "SELECT p.race_id,p.horse_id,p.decimal_odds,p.predicted_at,"
            "s.decimal_odds,s.observed_at,s.scheduled_post_time,"
            "s.source,s.source_reference "
            "FROM paper_prediction_evidence e "
            "JOIN predictions p ON p.id=e.prediction_id "
            "JOIN pre_race_odds_snapshots s ON s.id=e.odds_snapshot_id "
            "WHERE p.id=?",
            (int(prediction_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "race_id": row[0],
            "horse_id": row[1],
            "prediction_odds": row[2],
            "predicted_at": row[3],
            "snapshot_odds": row[4],
            "observed_at": row[5],
            "scheduled_post_time": row[6],
            "source": row[7],
            "source_reference": row[8],
        }

    def record_bet(self, d):
        cur = self.conn.execute(
            "INSERT INTO bets "
            "(race_id,horse_id,horse_name,bet_type,stake_yen,decimal_odds,"
            "expected_return_multiple,edge,reason,model_version,placed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (d.race_id,d.horse_id,d.horse_name,d.bet_type,d.stake_yen,d.decimal_odds,
             d.expected_return_multiple,d.edge,d.reason,d.model_version,
             datetime.now(timezone.utc).isoformat())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def record_paper_bet(
        self,
        decision,
        prediction_id,
        broker="paper",
        broker_reference="",
    ):
        row = self.conn.execute(
            "SELECT p.race_id,p.horse_id,p.decimal_odds "
            "FROM paper_prediction_evidence e "
            "JOIN predictions p ON p.id=e.prediction_id "
            "WHERE p.id=?",
            (int(prediction_id),),
        ).fetchone()
        if row is None:
            raise ValueError(
                "paper bet requires a prediction with linked pre-race evidence"
            )
        if decision.stake_yen <= 0:
            raise ValueError("paper bet stake must be positive")
        if decision.race_id != row[0] or decision.horse_id != row[1]:
            raise ValueError(
                "paper bet decision does not match prediction evidence"
            )
        if abs(float(decision.decimal_odds) - float(row[2])) > 1e-12:
            raise ValueError(
                "paper bet odds must match prediction evidence"
            )

        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO bets "
                "(race_id,horse_id,horse_name,bet_type,stake_yen,decimal_odds,"
                "expected_return_multiple,edge,reason,model_version,placed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    decision.race_id,
                    decision.horse_id,
                    decision.horse_name,
                    decision.bet_type,
                    int(decision.stake_yen),
                    float(decision.decimal_odds),
                    float(decision.expected_return_multiple),
                    float(decision.edge),
                    decision.reason,
                    decision.model_version,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            bet_id = int(cur.lastrowid)
            self.conn.execute(
                "INSERT INTO paper_bet_evidence "
                "(bet_id,prediction_id,broker,broker_reference,recorded_at) "
                "VALUES (?,?,?,?,?)",
                (
                    bet_id,
                    int(prediction_id),
                    broker,
                    broker_reference,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return bet_id

    def paper_bet_evidence(self, bet_id):
        row = self.conn.execute(
            "SELECT b.race_id,b.horse_id,b.stake_yen,b.decimal_odds,"
            "e.prediction_id,e.broker,e.broker_reference "
            "FROM paper_bet_evidence e "
            "JOIN bets b ON b.id=e.bet_id "
            "WHERE b.id=?",
            (int(bet_id),),
        ).fetchone()
        if row is None:
            return None
        return {
            "race_id": row[0],
            "horse_id": row[1],
            "stake_yen": row[2],
            "decimal_odds": row[3],
            "prediction_id": row[4],
            "broker": row[5],
            "broker_reference": row[6],
        }

    def unsettled_paper_bets(self):
        rows = self.conn.execute(
            "SELECT b.id,b.race_id,b.horse_id,b.horse_name,b.bet_type,"
            "b.stake_yen,b.decimal_odds,b.placed_at "
            "FROM bets b "
            "JOIN paper_bet_evidence e ON e.bet_id=b.id "
            "WHERE b.stake_yen > 0 AND b.result IS NULL "
            "ORDER BY b.id"
        ).fetchall()
        return [
            {
                "bet_id": int(row[0]),
                "race_id": row[1],
                "horse_id": row[2],
                "horse_name": row[3],
                "bet_type": row[4],
                "stake_yen": int(row[5]),
                "decimal_odds": float(row[6]),
                "placed_at": row[7],
            }
            for row in rows
        ]

    def record_paper_settlement(
        self,
        *,
        bet_id,
        race_id,
        horse_id,
        finish_position,
        final_win_odds,
        won,
        payout_yen,
        source,
        source_reference="",
    ):
        bet_id = int(bet_id)
        finish_position = int(finish_position)
        payout_yen = int(payout_yen)
        result = "WIN" if won else "LOSE"

        if finish_position <= 0:
            raise ValueError("finish_position must be positive")
        if payout_yen < 0:
            raise ValueError("payout_yen must not be negative")
        if not str(source).strip():
            raise ValueError("settlement source must not be empty")
        if won:
            if final_win_odds is None or float(final_win_odds) <= 1.0:
                raise ValueError(
                    "winning settlement requires valid final_win_odds"
                )
            if payout_yen <= 0:
                raise ValueError(
                    "winning settlement requires positive payout_yen"
                )
        elif payout_yen != 0:
            raise ValueError("losing settlement payout_yen must be zero")

        row = self.conn.execute(
            "SELECT b.race_id,b.horse_id,b.result,b.payout_yen "
            "FROM bets b "
            "JOIN paper_bet_evidence e ON e.bet_id=b.id "
            "WHERE b.id=?",
            (bet_id,),
        ).fetchone()
        if row is None:
            raise ValueError("settlement requires an existing Paper bet")
        if row[0] != race_id or row[1] != horse_id:
            raise ValueError("settlement identity does not match Paper bet")

        existing = self.conn.execute(
            "SELECT finish_position,final_win_odds,result,payout_yen,"
            "source,source_reference "
            "FROM paper_settlement_evidence WHERE bet_id=?",
            (bet_id,),
        ).fetchone()
        expected = (
            finish_position,
            None if final_win_odds is None else float(final_win_odds),
            result,
            payout_yen,
            str(source),
            str(source_reference),
        )
        if existing is not None:
            actual = (
                int(existing[0]),
                None if existing[1] is None else float(existing[1]),
                existing[2],
                int(existing[3]),
                existing[4],
                existing[5],
            )
            if actual != expected:
                raise ValueError(
                    "immutable settlement evidence conflict for bet"
                )
            return False

        if row[2] is not None:
            raise ValueError("Paper bet is already settled without evidence")

        with self.conn:
            self.conn.execute(
                "UPDATE bets SET result=?, payout_yen=? WHERE id=?",
                (result, payout_yen, bet_id),
            )
            self.conn.execute(
                "INSERT INTO paper_settlement_evidence "
                "(bet_id,race_id,horse_id,finish_position,final_win_odds,"
                "result,payout_yen,source,source_reference,recorded_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    bet_id,
                    race_id,
                    horse_id,
                    finish_position,
                    None if final_win_odds is None else float(final_win_odds),
                    result,
                    payout_yen,
                    str(source),
                    str(source_reference),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        return True

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
