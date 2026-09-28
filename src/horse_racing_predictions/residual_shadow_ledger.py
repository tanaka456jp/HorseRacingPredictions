from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from .residual_v12_shadow import evaluate_shadow_results


class ResidualShadowLedger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS shadow_rows (
                race_id TEXT NOT NULL,
                horse_id TEXT NOT NULL,
                post_position INTEGER NOT NULL,
                race_date TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                scheduled_post_time TEXT NOT NULL,
                decimal_odds REAL NOT NULL,
                market_probability REAL NOT NULL,
                residual_v12_probability REAL NOT NULL,
                overlay_ratio REAL NOT NULL,
                fixed_gamma REAL NOT NULL,
                finish_position INTEGER,
                PRIMARY KEY (race_id, horse_id)
            )
        """)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def record_predictions(self, predictions: pd.DataFrame) -> int:
        required = {
            "race_id",
            "horse_id",
            "post_position",
            "race_date",
            "observed_at",
            "scheduled_post_time",
            "decimal_odds",
            "market_probability",
            "residual_v12_probability",
            "overlay_ratio",
            "fixed_gamma",
        }
        missing = required - set(predictions.columns)
        if missing:
            raise ValueError(
                f"shadow ledger predictions missing columns: {sorted(missing)}"
            )

        inserted = 0
        for row in predictions.itertuples(index=False):
            values = (
                str(row.race_id),
                str(row.horse_id),
                int(row.post_position),
                str(pd.Timestamp(row.race_date).date()),
                pd.Timestamp(row.observed_at).isoformat(),
                pd.Timestamp(row.scheduled_post_time).isoformat(),
                float(row.decimal_odds),
                float(row.market_probability),
                float(row.residual_v12_probability),
                float(row.overlay_ratio),
                float(row.fixed_gamma),
            )
            existing = self.conn.execute(
                """
                SELECT post_position,race_date,observed_at,scheduled_post_time,
                       decimal_odds,market_probability,residual_v12_probability,
                       overlay_ratio,fixed_gamma
                FROM shadow_rows
                WHERE race_id=? AND horse_id=?
                """,
                values[:2],
            ).fetchone()
            if existing is not None:
                comparable = (
                    values[2],
                    values[3],
                    values[4],
                    values[5],
                    values[6],
                    values[7],
                    values[8],
                    values[9],
                    values[10],
                )
                if tuple(existing) != comparable:
                    raise ValueError(
                        "immutable shadow prediction conflict for "
                        f"{values[0]} / {values[1]}"
                    )
                continue

            self.conn.execute(
                """
                INSERT INTO shadow_rows (
                    race_id,horse_id,post_position,race_date,observed_at,
                    scheduled_post_time,decimal_odds,market_probability,
                    residual_v12_probability,overlay_ratio,fixed_gamma
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                values,
            )
            inserted += 1

        self.conn.commit()
        return inserted

    def record_results(self, results: pd.DataFrame) -> int:
        if results.empty:
            return 0
        required = {"race_id", "post_position", "finish_position"}
        missing = required - set(results.columns)
        if missing:
            raise ValueError(
                f"shadow ledger results missing columns: {sorted(missing)}"
            )

        frame = results[list(required)].copy()
        frame["race_id"] = frame["race_id"].astype(str)
        frame["post_position"] = pd.to_numeric(
            frame["post_position"], errors="raise"
        ).astype(int)
        frame["finish_position"] = pd.to_numeric(
            frame["finish_position"], errors="coerce"
        )
        frame = frame.dropna(subset=["finish_position"])
        frame["finish_position"] = frame["finish_position"].astype(int)
        frame = frame.drop_duplicates(
            ["race_id", "post_position"], keep=False
        )

        updated = 0
        for row in frame.itertuples(index=False):
            current = self.conn.execute(
                """
                SELECT finish_position FROM shadow_rows
                WHERE race_id=? AND post_position=?
                """,
                (row.race_id, row.post_position),
            ).fetchall()
            if not current:
                continue
            for (existing_finish,) in current:
                if existing_finish is not None:
                    if int(existing_finish) != int(row.finish_position):
                        raise ValueError(
                            "immutable shadow result conflict for "
                            f"{row.race_id} post {row.post_position}"
                        )
                    continue
                self.conn.execute(
                    """
                    UPDATE shadow_rows
                    SET finish_position=?
                    WHERE race_id=? AND post_position=?
                    """,
                    (
                        int(row.finish_position),
                        row.race_id,
                        int(row.post_position),
                    ),
                )
                updated += 1

        self.conn.commit()
        return updated

    def pending_race_ids(self) -> list[str]:
        rows = self.conn.execute(
            """
            SELECT race_id
            FROM shadow_rows
            GROUP BY race_id
            HAVING SUM(
                CASE WHEN finish_position IS NULL THEN 1 ELSE 0 END
            ) > 0
            ORDER BY race_id
            """
        ).fetchall()
        return [str(row[0]) for row in rows]

    def cumulative_frame(self) -> pd.DataFrame:
        return pd.read_sql_query(
            """
            SELECT race_id,horse_id,post_position,race_date,observed_at,
                   scheduled_post_time,decimal_odds,market_probability,
                   residual_v12_probability,overlay_ratio,fixed_gamma,
                   finish_position
            FROM shadow_rows
            ORDER BY race_date,race_id,post_position
            """,
            self.conn,
        )

    def cumulative_summary(self) -> dict:
        frame = self.cumulative_frame()
        if frame.empty:
            return {
                "status": "empty",
                "prediction_rows": 0,
                "prediction_races": 0,
                "evaluated_rows": 0,
                "evaluated_races": 0,
            }

        predictions = frame.drop(
            columns=["finish_position"]
        ).copy()
        results = frame.loc[
            frame["finish_position"].notna(),
            ["race_id", "post_position", "finish_position"],
        ].copy()
        evaluation = evaluate_shadow_results(
            predictions,
            results,
        )
        overlay = pd.to_numeric(
            frame["overlay_ratio"],
            errors="raise",
        )
        return {
            "status": evaluation["status"],
            "prediction_rows": int(len(frame)),
            "prediction_races": int(frame["race_id"].nunique()),
            "evaluated_rows": int(
                evaluation.get("evaluated_rows", 0)
            ),
            "evaluated_races": int(
                evaluation.get("evaluated_races", 0)
            ),
            "positive_overlay_rows": int(overlay.gt(0.0).sum()),
            "overlay_ge_5pct_rows": int(overlay.ge(0.05).sum()),
            "overlay_ge_10pct_rows": int(overlay.ge(0.10).sum()),
            "evaluation": evaluation,
        }
